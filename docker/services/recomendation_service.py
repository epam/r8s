import json
import os
from datetime import datetime, timedelta
from typing import Union, List, Dict
import itertools

import numpy as np
import pandas as pd

from commons.constants import STATUS_ERROR, STATUS_OK, OK_MESSAGE, \
    ACTION_SHUTDOWN, ACTION_SCHEDULE, ACTION_SPLIT, ACTION_EMPTY, \
    STATUS_POSTPONED, CURRENT_INSTANCE_TYPE_ATTR, CURRENT_MONTHLY_PRICE_ATTR, \
    SAVING_OPTIONS_ATTR, PROBABILITY, ALLOWED_ACTIONS, \
    GROUP_POLICY_AUTO_SCALING, TYPE_ATTR, JOB_STEP_PROCESS_METRICS, \
    THRESHOLDS_ATTR, MIN_ATTR, MAX_ATTR, DESIRED_ATTR, SCALE_STEP_ATTR, \
    ACTION_SCALE_DOWN, ACTION_SCALE_UP, SCALE_STEP_AUTO_DETECT, \
    COOLDOWN_DAYS_ATTR, ACTION_ERROR
from commons.exception import ExecutorException, ProcessingPostponedException
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.algorithm import Algorithm
from models.base_model import CloudEnum
from models.parent_attributes import LicensesParentMeta
from models.recommendation_history import RecommendationHistory, \
    RecommendationTypeEnum, RESOURCE_TYPE_GROUP
from models.shape import Shape
from models.shape_price import OSEnum
from services.environment_service import EnvironmentService
from services.meta_service import MetaService
from services.metrics_service import MetricsService
from services.recommendation_history_service import \
    RecommendationHistoryService
from services.resize.resize_service import ResizeService
from services.resize.resize_trend import ResizeTrend
from services.saving.saving_service import SavingService
from services.schedule.schedule_service import ScheduleService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-recommendation-service')

RIGHTSIZER_SOURCE = 'RIGHTSIZER'
RIGHTSIZER_RESOURCE_TYPE = 'INSTANCE'
RIGHTSIZER_AUTOSCALING_GROUP_RESOURCE_TYPE = 'AUTOSCALING_GROUP'
DEFAULT_SEVERITY = 'MEDIUM'
AUTOSCALING_METRICS = ('cpu_load', 'memory_load')


class RecommendationService:
    def __init__(self, metrics_service: MetricsService,
                 schedule_service: ScheduleService,
                 resize_service: ResizeService,
                 environment_service: EnvironmentService,
                 saving_service: SavingService,
                 meta_service: MetaService,
                 recommendation_history_service: RecommendationHistoryService,
                 shape_service: ShapeService):
        self.metrics_service = metrics_service
        self.schedule_service = schedule_service
        self.resize_service = resize_service
        self.environment_service = environment_service
        self.saving_service = saving_service
        self.meta_service = meta_service
        self.recommendation_history_service = recommendation_history_service
        self.shape_service = shape_service

        self.policy_type_processor = {
            GROUP_POLICY_AUTO_SCALING: self.process_autoscaling_group
        }

    @profiler(execution_step=f'instance_recommendation_generation')
    def process_instance(self, metric_file_path, algorithm: Algorithm,
                         reports_dir, instance_meta_mapping=None,
                         parent_meta: Union[None, LicensesParentMeta] = None):
        _LOG.debug(f'Parsing entity names from metrics file path '
                   f'\'{metric_file_path}\'')
        df = None
        schedule = None
        recommended_sizes = None
        resize_action = None
        savings = None
        advanced = None
        history_items = None

        allowed_actions = algorithm.recommendation_settings.allowed_actions

        customer, cloud, tenant, region, _, instance_id = self.parse_folders(
            metric_file_path=metric_file_path
        )
        if cloud.upper() != CloudEnum.CLOUD_GOOGLE.value:
            instance_os = OSEnum.OS_LINUX.value
        else:
            # use Linux pricing as a default for all clouds except GCP
            instance_os = None

        instance_meta = {}
        if instance_meta_mapping:
            instance_meta = instance_meta_mapping.get(instance_id)

        _LOG.debug(f'Instance meta: {instance_meta}')

        _LOG.debug('Loading past recommendation with feedback')
        past_recommendations_feedback = self.recommendation_history_service. \
            get_recommendation_with_feedback(instance_id=instance_id)

        applied_recommendations = self.recommendation_history_service. \
            filter_applied(recommendations=past_recommendations_feedback)
        try:
            _LOG.debug('Loading adjustments from meta')
            meta_adjustments = self.meta_service.to_adjustments(
                instance_meta=instance_meta
            )
            applied_recommendations.extend(meta_adjustments)
            _LOG.debug('Loading df')
            df = self.metrics_service.load_df(
                path=metric_file_path,
                algorithm=algorithm,
                applied_recommendations=applied_recommendations,
                instance_meta=instance_meta
            )

            _LOG.debug('Extracting instance type name')
            instance_type = self.metrics_service.get_instance_type(
                metric_file_path=metric_file_path,
                algorithm=algorithm
            )
            _LOG.debug('Dividing into periods with different load')
            shutdown_periods, low_periods, medium_periods, \
                high_periods, centroids = \
                self.metrics_service.divide_on_periods(
                    df=df,
                    algorithm=algorithm)

            _LOG.debug(f'Got {len(high_periods)} high-load, '
                       f'{len(low_periods)} low-load periods')
            non_straight_periods, total_length = self.get_non_straight_periods(
                df=df,
                grouped_periods=(low_periods, medium_periods, high_periods)
            )
            if (non_straight_periods and total_length and
                    ACTION_SPLIT in allowed_actions):
                _LOG.debug('Calculating resize trends for several loads')
                trends = self.metrics_service. \
                    calculate_instance_trend_multiple(
                    algorithm=algorithm,
                    non_straight_periods=non_straight_periods,
                    total_length=total_length
                )
            else:
                _LOG.debug('Generating resize trend')
                if any((low_periods, medium_periods, high_periods)):
                    df_ = pd.concat([*low_periods, *medium_periods,
                                     *high_periods])
                else:
                    df_ = df
                trends = self.metrics_service.calculate_instance_trend(
                    df=df_,
                    algorithm=algorithm
                )
                trends = [trends]
            _LOG.debug(f'Resize trend for instance \'{instance_id}\' has been '
                       f'calculated. ')

            _LOG.debug(
                f'Got {len(shutdown_periods)} shutdown periods to process')
            _LOG.debug(f'Generating schedule for instance \'{instance_id}\'')
            if not low_periods and not medium_periods and not high_periods:
                schedule = []
            elif ACTION_SCHEDULE in allowed_actions:
                schedule = self.schedule_service.generate_schedule(
                    shutdown_periods=shutdown_periods,
                    recommendation_settings=algorithm.recommendation_settings,
                    instance_id=instance_id,
                    df=df,
                    instance_meta=instance_meta,
                    past_recommendations=applied_recommendations
                )
            else:
                schedule = self.schedule_service.get_always_run_schedule()

            _LOG.debug('Searching for resize action')
            resize_action = ResizeTrend.get_resize_action(trends=trends)

            _LOG.debug('Searching for better-fix instance types')
            compatibility_rule = algorithm.recommendation_settings. \
                shape_compatibility_rule
            _LOG.debug(f'Shape compatibility rule to be applied: '
                       f'{compatibility_rule}')

            past_resize_recommendations = self.recommendation_history_service. \
                filter_resize(recommendations=applied_recommendations)
            if len(trends) == 1:
                max_recommended_shapes = algorithm.recommendation_settings. \
                    max_recommended_shapes
                recommended_sizes = self.resize_service.recommend_size(
                    trend=trends[0],
                    instance_type=instance_type,
                    algorithm=algorithm,
                    cloud=cloud.upper(),
                    instance_meta=instance_meta,
                    resize_action=resize_action,
                    parent_meta=parent_meta,
                    max_results=max_recommended_shapes,
                    shape_compatibility_rule=compatibility_rule,
                    past_resize_recommendations=past_resize_recommendations
                )
            else:
                recommended_sizes = []
                for trend in trends:
                    recommended_size = self.resize_service.recommend_size(
                        trend=trend,
                        instance_type=instance_type,
                        algorithm=algorithm,
                        cloud=cloud.upper(),
                        instance_meta=instance_meta,
                        resize_action=resize_action,
                        parent_meta=parent_meta,
                        max_results=1,
                        shape_compatibility_rule=compatibility_rule,
                        past_resize_recommendations=past_resize_recommendations
                    )
                    recommended_sizes.extend(recommended_size)
            recommended_sizes = self.resize_service.add_price(
                instances=recommended_sizes,
                customer=customer,
                region=region,
                os=instance_os)

            recommended_sizes = self._cleanup_recommended_shapes(
                recommended_sizes=recommended_sizes,
                current_instance_type=instance_type,
                allow_same_shape=resize_action == ACTION_SPLIT
            )
            recommended_sizes = self.resize_service.sort_shapes(
                shapes=recommended_sizes,
                sort_option=algorithm.recommendation_settings.shape_sorting
            )
            _LOG.debug(f'Got {len(recommended_sizes)} '
                       f'recommended instance types')

            _LOG.debug(f'Calculate instance stats')
            stats = self.calculate_instance_stats(df=df)
            advanced = self.calculate_advanced_stats(
                df=df,
                centroids=centroids,
                algorithm=algorithm
            )
            general_action = self.get_general_action(
                schedule=schedule,
                shapes=recommended_sizes,
                resize_action=resize_action,
                stats=stats,
                past_recommendations=past_recommendations_feedback,
                allowed_actions=allowed_actions
            )

            if not algorithm.recommendation_settings.ignore_savings:
                _LOG.debug(f'Calculating savings')
                savings = self.saving_service.calculate_savings(
                    general_actions=general_action,
                    current_shape=instance_type,
                    recommended_shapes=recommended_sizes,
                    schedule=schedule,
                    customer=customer,
                    region=region,
                    os=instance_os
                )
            try:
                _LOG.debug(f'Saving recommendation to history')
                history_items = self.recommendation_history_service.create(
                    resource_id=instance_id,
                    job_id=self.environment_service.get_batch_job_id(),
                    customer=customer,
                    tenant=tenant,
                    region=region,
                    schedule=schedule,
                    recommended_shapes=recommended_sizes,
                    current_instance_type=instance_type,
                    savings=savings,
                    actions=general_action,
                    instance_meta=instance_meta,
                    last_metric_capture_date=df.index.max().date()
                )
            except Exception as e:
                _LOG.error(f'Exception occurred while processing history '
                           f'items: {str(e)}')
        except Exception as e:
            _LOG.debug(f'Calculate instance stats with exception')
            stats = self.calculate_instance_stats(df=df, exception=e)
            general_action = self.get_general_action(
                schedule=schedule,
                shapes=recommended_sizes,
                resize_action=resize_action,
                stats=stats)

        _LOG.debug(f'Dumping instance results')
        item = self.format_recommendation(
            instance_id=instance_id,
            schedule=schedule,
            recommended_sizes=recommended_sizes,
            stats=stats,
            meta=instance_meta,
            general_action=general_action,
            savings=savings,
            advanced=advanced
        )
        return item, history_items

    def process_group_resources(self, group_id: str,
                                group_policy: dict,
                                metric_file_paths: List[str],
                                algorithm: Algorithm, reports_dir,
                                instance_meta_mapping):
        group_policy_type = group_policy.get(TYPE_ATTR)

        processor = self.policy_type_processor.get(group_policy_type)

        if not processor:
            _LOG.error(f'Invalid group policy type {group_policy_type}. '
                       f'Supported types: '
                       f'{list(self.policy_type_processor.keys())}')
            raise ExecutorException(
                step_name=JOB_STEP_PROCESS_METRICS,
                reason=f'Invalid group policy type {group_policy_type}. '
                       f'Supported types: '
                       f'{list(self.policy_type_processor.keys())}'
            )

        processor(
            group_id=group_id,
            group_policy=group_policy,
            metric_file_paths=metric_file_paths,
            algorithm=algorithm,
            reports_dir=reports_dir,
            instance_meta_mapping=instance_meta_mapping
        )

    def process_autoscaling_group(self, group_id: str,
                                  group_policy: dict,
                                  metric_file_paths: List[str],
                                  algorithm: Algorithm, reports_dir,
                                  instance_meta_mapping: dict):
        _LOG.debug(f'Loading group resources: {metric_file_paths}')

        customer, cloud, tenant, region, _, instance_id = self.parse_folders(
            metric_file_path=metric_file_paths[0]
        )

        recent_recommendations = self.recommendation_history_service.get_recent_recommendation(
            resource_id=group_id,
            resource_type=RESOURCE_TYPE_GROUP,
            limit=1
        )
        if recent_recommendations:
            last_recommendation = next(iter(recent_recommendations))
            generated_at = last_recommendation.added_at
            cooldown_days = group_policy.get('cooldown_days')

            cooldown_passed = self._cooldown_period_passed(
                last_scan_date=generated_at,
                cooldown_days=cooldown_days)
            if not cooldown_passed:
                _LOG.debug('Cooldown period is not passed yet, '
                           'past recommendation will be used')
                self.dump_group_report_from_recommendation(
                    reports_dir=reports_dir,
                    group_policy=group_policy,
                    cloud=cloud,
                    region=region,
                    recommendation=last_recommendation
                )
                return

        dfs = {}
        instance_type_mapping = {}  # instance_type: List[instance_id]
        id_file_mapping = {}
        failed_resources = {}
        for metric_file_path in metric_file_paths:
            instance_id = self.get_instance_id(
                metric_file_path=metric_file_path)
            id_file_mapping[instance_id] = metric_file_path
            _LOG.debug(f'Loading df: {metric_file_path}')
            try:
                df = self.metrics_service.load_df(
                    path=metric_file_path,
                    algorithm=algorithm,
                    instance_meta=instance_meta_mapping.get(instance_id, {}),
                    max_days=group_policy.get(COOLDOWN_DAYS_ATTR)
                )
                dfs[instance_id] = df
            except ExecutorException as e:
                _LOG.debug(f'Exception occurred while reading metric file: '
                           f'{metric_file_path}. Error: {e}')
                failed_resources[instance_id] = e
                continue

            _LOG.debug('Extracting instance type name')
            instance_type = self.metrics_service.get_instance_type(
                metric_file_path=metric_file_path,
                algorithm=algorithm
            )
            if instance_type not in instance_type_mapping:
                instance_type_mapping[instance_type] = [instance_id]
            else:
                instance_type_mapping[instance_type].append(instance_id)

        target_instance_type, target_resources, non_matching_resources = (
            self._find_non_matching_autoscaling_resources(
                instance_type_mapping=instance_type_mapping
            ))

        target_resources = self._filter_outdated_resources(
            target_resources=target_resources,
            dfs=dfs
        )

        if non_matching_resources:
            _LOG.debug('Dumping non-matching autoscaling group resources')
            self.dump_autoscaling_resources(
                instance_type_mapping=instance_type_mapping,
                non_matching_resources=non_matching_resources,
                dfs=dfs,
                instance_meta_mapping=instance_meta_mapping,
                id_file_mapping=id_file_mapping,
                reports_dir=reports_dir,
                action=ACTION_SHUTDOWN
            )
        if failed_resources:
            _LOG.debug('Dumping failed autoscaling group resource')
            self.dump_autoscaling_failed_resources(
                instance_type_mapping=instance_type_mapping,
                failed_resources=failed_resources,
                instance_meta_mapping=instance_meta_mapping,
                id_file_mapping=id_file_mapping,
                reports_dir=reports_dir
            )

        _LOG.debug('Dumping autoscaling group resources as NO_ACTION')
        self.dump_autoscaling_resources(
            instance_type_mapping=instance_type_mapping,
            non_matching_resources=target_resources,
            dfs=dfs,
            instance_meta_mapping=instance_meta_mapping,
            id_file_mapping=id_file_mapping,
            reports_dir=reports_dir,
            action=ACTION_EMPTY
        )

        _LOG.debug(f'Describing target group shape: {target_instance_type}')
        target_shape = self.shape_service.get(name=target_instance_type)

        dfs = [dfs[instance_id] for instance_id in dfs.keys()
               if instance_id in target_resources]

        _LOG.debug('Detecting scaling action')
        scale_action, scale_step = self.get_autoscaling_group_scale_action(
            dfs=dfs,
            group_policy=group_policy,
            algorithm=algorithm,
            instance_type=target_instance_type
        )
        _LOG.debug(f'Scaling action: {scale_action}, scale step: {scale_step}')

        if (scale_action == ACTION_SCALE_DOWN and
                scale_step >= len(target_resources)):
            policy_scale_step = group_policy.get(SCALE_STEP_ATTR)
            if policy_scale_step == SCALE_STEP_AUTO_DETECT:
                _LOG.debug('Scaling down to single group resource '
                           'will be recommended')
                scale_step = len(target_resources) - 1
            else:
                _LOG.debug('Scale down is blocked due to lack of '
                           'available resources and strict scale step.')
                scale_action = ACTION_EMPTY
                scale_step = 0

        _LOG.debug(f'Filtering instance meta mapping to include '
                   f'only active group resources')
        target_resources_meta_mapping = {resource_id: v for resource_id, v in
                                         instance_meta_mapping.items()
                                         if resource_id in target_resources}
        _LOG.debug(f'Target resources meta mapping: '
                   f'{target_resources_meta_mapping}')

        _LOG.debug(f'Formatting autoscaling group {group_id} recommendation')
        item = self.format_autoscaling_recommendation(
            group_id=group_id,
            group_policy=group_policy,
            shape=target_shape,
            action=scale_action,
            instance_meta_mapping=target_resources_meta_mapping,
            current_resources=target_resources,
            scale_step=scale_step,
            dfs=dfs
        )

        _LOG.debug('Saving group recommendation')
        self.save_report(
            reports_dir=reports_dir,
            customer=customer,
            cloud=cloud,
            tenant=tenant,
            region=region,
            item=item
        )

        last_captured_date = None
        last_captured_date_str = item.get('stats', {}).get('to_date')
        if last_captured_date_str:
            last_captured_date = datetime.fromisoformat(last_captured_date_str)

        _LOG.debug(f'Saving group recommendation to db')
        history_item = self.recommendation_history_service.create_group_recommendation(
            resource_id=group_id,
            job_id=self.environment_service.get_batch_job_id(),
            customer=customer,
            tenant=tenant,
            region=region,
            current_instance_type=target_instance_type,
            instance_meta=target_resources_meta_mapping,
            last_metric_capture_date=last_captured_date,
            action=scale_action,
            recommendation=item.get('recommendation')
        )
        self.recommendation_history_service.save(recommendation=history_item)

    def divide_by_group_policies(self, metric_file_paths: List[str],
                                 instance_meta_mapping: dict,
                                 group_policies: List[dict]):
        group_resources_mapping = {}
        individual_resources = []
        allowed_group_tags = {policy.get('tag'): policy.get('id') for policy in
                              group_policies if policy.get('tag')}

        for metric_file_path in metric_file_paths:
            resource_id = self.get_instance_id(
                metric_file_path=metric_file_path)
            instance_meta = instance_meta_mapping.get(resource_id, {})
            instance_tags = self.meta_service.parse_tags(
                instance_meta=instance_meta)

            for tag_key, policy_id in allowed_group_tags.items():
                if tag_key in instance_tags:
                    tag_value = instance_tags[tag_key]
                    if policy_id not in group_resources_mapping:
                        group_resources_mapping[policy_id] = {}
                    if tag_value not in group_resources_mapping[policy_id]:
                        group_resources_mapping[policy_id][tag_value] = []
                    group_resources_mapping[policy_id][tag_value].append(
                        metric_file_path)
                    break
            else:
                individual_resources.append(metric_file_path)
        return group_resources_mapping, individual_resources

    def dump_error_report(self, reports_dir, metric_file_path,
                          exception):
        customer, cloud, tenant, region, _, instance_id = self.parse_folders(
            metric_file_path=metric_file_path
        )
        stats = self.calculate_instance_stats(exception=exception)
        item = self.format_recommendation(
            instance_id=instance_id,
            schedule=[],
            recommended_sizes=[],
            stats=stats,
            meta={},
            general_action=STATUS_ERROR
        )
        return self.save_report(
            reports_dir=reports_dir,
            customer=customer,
            cloud=cloud,
            tenant=tenant,
            region=region,
            item=item
        )

    def format_autoscaling_recommendation(
            self, group_id: str, group_policy: dict, shape: Shape, action: str,
            instance_meta_mapping: dict, current_resources: List[str],
            scale_step: int, dfs: List[pd.DataFrame] = None):
        recommended_count = len(current_resources)
        if action == ACTION_SCALE_UP:
            recommended_count += scale_step
        elif action == ACTION_SCALE_DOWN:
            recommended_count -= scale_step

        meta = {instance_id: instance_meta_mapping.get(instance_id, {})
                for instance_id in current_resources}

        _LOG.debug('Calculating autoscaling group stats')
        stats = self.calculate_instance_group_stats(
            dfs=dfs,
            resources=current_resources)

        item = {
            'resource_id': group_id,
            'resource_type': RIGHTSIZER_AUTOSCALING_GROUP_RESOURCE_TYPE,
            'source': RIGHTSIZER_SOURCE,
            'severity': DEFAULT_SEVERITY,
            'recommendation': {
                'instance_type': shape.get_dto(),
                'current_resources': len(current_resources),
                'recommended_resources': recommended_count
            },
            'stats': stats,
            'policies': [
                group_policy
            ],
            'general_actions': [
                action
            ],
            'meta': meta
        }
        _LOG.debug(f'Formatted item: {item}')
        return item

    def format_recommendation(self, stats, instance_id=None, schedule=None,
                              recommended_sizes=None, meta=None,
                              general_action=None,
                              savings=None, advanced=None):
        if general_action and not isinstance(general_action, list):
            general_action = [general_action]
        item = {
            'resource_id': instance_id,
            'resource_type': RIGHTSIZER_RESOURCE_TYPE,
            'source': RIGHTSIZER_SOURCE,
            'severity': DEFAULT_SEVERITY,
            'recommendation': {
                'schedule': schedule,
                'recommended_shapes': recommended_sizes,
                'savings': savings,
                'advanced': advanced,
            },
            'stats': stats,
            'meta': meta,
            'general_actions': general_action
        }
        self.prettify_recommendation(recommendation_item=item)
        return item

    @staticmethod
    def save_report(reports_dir, customer, cloud, tenant, region, item):
        dir_path = os.path.join(reports_dir, customer, cloud, tenant)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f'{region}.jsonl')
        with open(file_path, 'a') as f:
            f.write(json.dumps(item))
            f.write('\n')

    def save_history_items(self, history_items: List[RecommendationHistory]):
        _LOG.debug(f'Saving \'{len(history_items)}\' history items')
        try:
            self.recommendation_history_service.batch_save(
                recommendations=history_items)
        except Exception as e:
            _LOG.error(f'Exception occurred while saving recommendation '
                       f'to history: {str(e)}')

    def dump_reports_from_recommendations(
            self, reports_dir, cloud,
            recommendations: List[RecommendationHistory]):
        schedule = None
        recommended_sizes = None
        actions = []

        stats = self.generate_past_recommendation_stats(
            recommendations=recommendations
        )

        for recommendation_item in recommendations:
            recommendation_type = recommendation_item.recommendation_type
            if recommendation_type == RecommendationTypeEnum.ACTION_SCHEDULE:
                schedule = recommendation_item.recommendation
            elif recommendation_type == RecommendationTypeEnum.ACTION_SHUTDOWN:
                schedule = []
            elif recommendation_type == RecommendationTypeEnum.ACTION_EMPTY:
                recommended_sizes = recommendation_item.recommendation
            elif recommendation_type in RecommendationTypeEnum.resize():
                recommended_sizes = recommendation_item.recommendation
            actions.append(recommendation_item.recommendation_type.value)

        savings = {
            CURRENT_INSTANCE_TYPE_ATTR:
                recommendations[0].current_instance_type,
            CURRENT_MONTHLY_PRICE_ATTR:
                recommendations[0].current_month_price_usd,
            SAVING_OPTIONS_ATTR: list(itertools.chain.from_iterable(
                [r.savings for r in recommendations]
            ))
        }
        if schedule is None:
            schedule = self.schedule_service.get_always_run_schedule()

        item = self.format_recommendation(
            instance_id=recommendations[0].resource_id,
            stats=stats,
            schedule=schedule,
            recommended_sizes=recommended_sizes,
            meta=recommendations[0].instance_meta,
            general_action=actions,
            savings=savings
        )
        return self.save_report(
            reports_dir=reports_dir,
            customer=recommendations[0].customer,
            cloud=cloud,
            tenant=recommendations[0].tenant,
            region=recommendations[0].region,
            item=item
        )

    def dump_group_report_from_recommendation(self, reports_dir, cloud,
                                              region, group_policy,
                                              recommendation: RecommendationHistory):
        shape_name = recommendation.current_instance_type
        shape = self.shape_service.get(name=shape_name)

        recommendation_data = recommendation.recommendation[0]
        recommended_resources = recommendation_data.get(
            'recommended_resources')
        current_resources = list(recommendation.instance_meta.keys())

        _LOG.debug('Formatting group recommendation from history')
        item = self.format_autoscaling_recommendation(
            group_id=recommendation.resource_id,
            group_policy=group_policy,
            shape=shape,
            action=recommendation.recommendation_type.value,
            instance_meta_mapping=recommendation.instance_meta,
            current_resources=current_resources,
            scale_step=abs(len(current_resources) - recommended_resources)
        )
        _LOG.debug(f'Saving group recommendation: '
                   f'{recommendation.resource_id}')
        self.save_report(
            reports_dir=reports_dir,
            customer=recommendation.customer,
            cloud=cloud,
            tenant=recommendation.tenant,
            region=region,
            item=item
        )
        _LOG.debug('Formatting recommendation for each group resource')
        for resource_id in current_resources:
            _LOG.debug(
                f'Formatting recommendation for resource: {resource_id}')
            resource_item = self.format_recommendation(
                stats=self.calculate_instance_stats(),
                instance_id=resource_id,
                schedule=self.schedule_service.get_always_run_schedule(),
                recommended_sizes=[],
                general_action=ACTION_EMPTY,
                savings=self.saving_service.calculate_savings(
                    general_actions=ACTION_EMPTY,
                    current_shape=recommendation.current_instance_type,
                    recommended_shapes=[],
                    schedule=None,
                    customer=recommendation.customer,
                    region=region,
                    os=OSEnum.OS_LINUX.value
                ),
                meta=recommendation.instance_meta.get(resource_id, {})
            )
            _LOG.debug(f'Saving recommendation for resource: {resource_id}')
            self.save_report(
                reports_dir=reports_dir,
                customer=recommendation.customer,
                cloud=cloud,
                tenant=recommendation.tenant,
                region=region,
                item=resource_item
            )

    @staticmethod
    def get_non_straight_periods(df, grouped_periods):
        total_length = len(df)
        valid_period_groups = []
        total_valid_period_len = 0
        for periods in grouped_periods:
            grouped_len = sum([len(period) for period in
                               periods])  # metrics are in 5min freq, periods are in 10min
            if grouped_len >= total_length * 0.05:
                # eq 10%, period metrics are 10min freq, df freq is 5min
                valid_period_groups.append(periods)
                total_valid_period_len += grouped_len

        if not valid_period_groups or len(valid_period_groups) == 1:
            return None, None

        return valid_period_groups, total_valid_period_len

    @staticmethod
    def calculate_instance_stats(df=None, exception=None):
        from_date = None
        to_date = None

        if df is not None:
            from_date = min(df.T).to_pydatetime().isoformat()
            to_date = max(df.T).to_pydatetime().isoformat()

        if isinstance(exception, ExecutorException):
            status = STATUS_ERROR
            message = exception.reason
        elif isinstance(exception, ProcessingPostponedException):
            status = STATUS_POSTPONED
            message = str(exception)
        elif exception:
            status = STATUS_ERROR
            message = f'Unexpected error occurred: {str(exception)}'
        else:
            status = STATUS_OK
            message = OK_MESSAGE

        return {
            'from_date': from_date,
            'to_date': to_date,
            'status': status,
            'message': message
        }

    @staticmethod
    def calculate_instance_group_stats(dfs: List[pd.DataFrame] = None,
                                       resources: List[str] = None,
                                       exception=None):
        from_date = None
        to_date = None

        if dfs:
            for df in dfs:
                df_from_date = min(df.T).to_pydatetime().isoformat()
                df_to_date = max(df.T).to_pydatetime().isoformat()

                if not from_date or df_from_date < from_date:
                    from_date = df_from_date
                if not to_date or df_to_date > to_date:
                    to_date = df_to_date

        if isinstance(exception, ExecutorException):
            status = STATUS_ERROR
            message = exception.reason
        elif isinstance(exception, ProcessingPostponedException):
            status = STATUS_POSTPONED
            message = str(exception)
        elif exception:
            status = STATUS_ERROR
            message = f'Unexpected error occurred: {str(exception)}'
        else:
            status = STATUS_OK
            message = OK_MESSAGE

        return {
            'resources': resources or [],
            'from_date': from_date,
            'to_date': to_date,
            'status': status,
            'message': message
        }

    @staticmethod
    def generate_past_recommendation_stats(
            recommendations: List[RecommendationHistory]):
        last_captured_date = max([rec.last_metric_capture_date
                                  for rec in recommendations])
        return {
            'from_date': None,
            'to_date': last_captured_date.isoformat(),
            'status': STATUS_OK,
            'message': OK_MESSAGE
        }

    def calculate_advanced_stats(self, df, algorithm, centroids):
        _LOG.debug('Calculating advanced stats')
        result = {}

        metric_fields = self._get_metric_fields(df=df, algorithm=algorithm)
        for metric_field in metric_fields:
            _LOG.debug(f'Calculating advanced stats for {metric_field}')
            metric_stats = self._get_metric_advanced_stats(
                df=df,
                metric_name=metric_field
            )
            if metric_stats:
                _LOG.debug(f'{metric_field} advanced stats: {metric_stats}')
                result[metric_field] = metric_stats

        _LOG.debug('Calculating clustering stats')
        cluster_stats = self._get_clusters_stats(centroids=centroids)
        _LOG.debug(f'Clustering stats: {cluster_stats}')
        result['clusters'] = cluster_stats

        return result

    @staticmethod
    def parse_folders(metric_file_path):
        """
        Extracts customer, tenant, region, timestamp and instance id from
        metric file path
        """
        file_name = os.path.basename(metric_file_path)
        folders = metric_file_path.split(os.sep)

        instance_id = folders[-1][0:file_name.rindex('.')]
        timestamp = folders[-2]
        region = folders[-3]
        tenant = folders[-4]
        cloud = folders[-5]
        customer = folders[-6]

        return customer, cloud, tenant, region, timestamp, instance_id

    @staticmethod
    def get_instance_id(metric_file_path: str):
        file_name = metric_file_path.split(os.sep)[-1]
        return file_name[0:file_name.rindex('.')]

    def get_general_action(self, schedule, shapes, stats, resize_action,
                           allowed_actions: list = ALLOWED_ACTIONS,
                           past_recommendations: list = None):
        actions = []
        status = stats.get('status', '')
        if status == STATUS_POSTPONED:
            return [ACTION_EMPTY]
        if status != STATUS_OK:
            return [STATUS_ERROR]

        shutdown_forbidden = ACTION_SHUTDOWN not in allowed_actions
        if not shutdown_forbidden and past_recommendations:
            shutdown_forbidden = self.recommendation_history_service. \
                is_shutdown_forbidden(
                recommendations=past_recommendations
            )

        if not schedule and not shutdown_forbidden:
            return [ACTION_SHUTDOWN]

        if (schedule and ACTION_SCHEDULE in allowed_actions and not
        self._is_schedule_always_run(schedule=schedule)):
            actions.append(ACTION_SCHEDULE)

        if shapes:
            is_split = np.isclose(
                sum([shape.get(PROBABILITY, 0.0) for shape in shapes]),
                1.0, rtol=1e-09, atol=1e-09)
            if is_split:
                actions.append(ACTION_SPLIT)
            elif resize_action in allowed_actions:
                actions.append(resize_action)

        if not actions:
            return [ACTION_EMPTY]
        return actions

    @staticmethod
    def _is_schedule_always_run(schedule, complete_week=True):
        if len(schedule) != 1:
            return False
        schedule = schedule[0]
        start = schedule.get('start', '')
        stop = schedule.get('stop', '')
        weekdays = schedule.get('weekdays', [])

        if complete_week:
            stop_suits = stop.startswith('23:') or stop == '00:00'
            return start == '00:00' and stop_suits and len(weekdays) == 7
        return start == '00:00' and stop.startswith('23:')

    def prettify_recommendation(self, recommendation_item):
        recommendation = recommendation_item.get('recommendation')
        schedule = recommendation.get('schedule')
        shapes = recommendation.get('recommended_shapes')
        if shapes is None:
            recommendation['recommended_shapes'] = []
        if schedule is None:
            recommendation['schedule'] = []
        if schedule:
            schedule.sort(key=lambda k: self._get_schedule_weight(k))
            if len(schedule) > 5:
                schedule = schedule[0:5]
            recommendation['schedule'] = schedule
        if not recommendation['advanced']:
            recommendation.pop('advanced', None)
        recommendation_item['recommendation'] = recommendation

    @staticmethod
    def _get_schedule_weight(schedule_item):
        start = schedule_item.get('start')
        stop = schedule_item.get('stop')
        start_dt = datetime.strptime(start, '%H:%M')
        stop_dt = datetime.strptime(stop, '%H:%M')

        delta = (stop_dt - start_dt).total_seconds()
        return delta * len(schedule_item.get('weekdays'))

    @staticmethod
    def _cleanup_recommended_shapes(recommended_sizes,
                                    current_instance_type,
                                    allow_same_shape=False):
        result = []

        for size in recommended_sizes:
            instance_type = size.get('name')
            if size in result:
                continue
            if not allow_same_shape and instance_type == current_instance_type:
                continue
            result.append(size)
        return result

    @staticmethod
    def _get_metric_fields(df: pd.DataFrame, algorithm: Algorithm):
        valid_columns = []
        for column in list(algorithm.metric_attributes):
            if any([value not in (0, -1) for value in df['cpu_load']]):
                valid_columns.append(column)
        return valid_columns

    @staticmethod
    def _get_metric_advanced_stats(df: pd.DataFrame, metric_name):
        series = df[metric_name]

        deciles = list(np.quantile(series, np.arange(0.1, 1, 0.1))),
        deciles = [round(float(decile), 2) for decile in deciles[0]]

        return {
            "min": round(float(np.max(series)), 2),
            "max": round(float(np.max(series)), 2),
            "mean": round(float(np.mean(series)), 2),
            "deciles": deciles,
            "variance": round(float(np.var(series)), 2),
            "standard_deviation": round(float(np.std(series)), 2)
        }

    @staticmethod
    def _get_clusters_stats(centroids: list):
        cluster_count_per_day = [len(day_centroids)
                                 for day_centroids in centroids]
        if not centroids:
            return {}
        quartiles = list(np.quantile(cluster_count_per_day,
                                     np.arange(0.25, 1, 0.25))),
        quartiles = [round(float(quartile), 2) for quartile in quartiles[0]]
        return {
            "avg_per_day": round(float(np.average(cluster_count_per_day)), 2),
            "max_per_day": round(float(np.max(cluster_count_per_day)), 2),
            "min_per_day": round(float(np.min(cluster_count_per_day)), 2),
            "quartiles": quartiles
        }

    @staticmethod
    def _find_non_matching_autoscaling_resources(
            instance_type_mapping: Dict[str, List[str]]):
        """

        Args:
            instance_type_mapping: map of instance type to
                list of resource id with that instance type

        Returns:
            Tuple:
            0 - target autoscaling group instance type
            1 - target autoscaling group resources (of target instance type)
            2 - resources with different instance type from
                the most common in group
        """
        _LOG.debug('Sorting group resources by the amount of resources')
        instance_type_mapping = {k: v for k, v in
                                 sorted(instance_type_mapping.items(),
                                        key=lambda item: -len(item[1]))}
        _LOG.debug(f'Instance type mapping: {instance_type_mapping}')
        if len(instance_type_mapping) == 1:
            instance_type = next(iter(instance_type_mapping))
            _LOG.debug(f'Auto scaling group consist from resources with '
                       f'same instance type: {instance_type}')
            return instance_type, instance_type_mapping[instance_type], []
        target_type = None
        non_matching_resources = []
        for instance_type, resources in instance_type_mapping.items():
            if not target_type:
                target_type = instance_type
            elif len(resources) == len(instance_type_mapping[target_type]):
                _LOG.warning(f'Several different instance types with same '
                             f'amount of resources detected: {target_type}, '
                             f'{instance_type}. Autoscaling policy '
                             f'won\'t be applied.')
                return (None, [],
                        list(itertools.chain(*instance_type_mapping.values())))
            else:
                non_matching_resources.extend(
                    instance_type_mapping[instance_type])

        _LOG.debug(f'Non matching resources: {non_matching_resources}')
        return (target_type, instance_type_mapping[target_type],
                non_matching_resources)

    def dump_autoscaling_resources(
            self, instance_type_mapping: dict,
            non_matching_resources: list,
            dfs: Dict[str, pd.DataFrame],
            instance_meta_mapping: dict,
            id_file_mapping: dict,
            reports_dir: str,
            action: str
    ):
        id_type_mapping = {}
        for instance_type, resources in instance_type_mapping.items():
            for instance_id in resources:
                id_type_mapping[instance_id] = instance_type

        _LOG.warning(f'Resources with non-matching instance type for auto '
                     f'scaling group: {non_matching_resources}. '
                     f'Dumping as SHUTDOWN recommendations')
        for instance_id in non_matching_resources:
            customer, cloud, tenant, region, _, instance_id = self.parse_folders(
                metric_file_path=id_file_mapping.get(instance_id)
            )

            formatted_item = self.format_recommendation(
                stats=self.calculate_instance_stats(dfs[instance_id]),
                instance_id=instance_id,
                general_action=action,
                meta=instance_meta_mapping.get(instance_id, {}),
                savings=self.saving_service.calculate_savings(
                    general_actions=[action],
                    current_shape=id_type_mapping.get(instance_id),
                    schedule=[],
                    recommended_shapes=[],
                    customer=customer,
                    region=region,
                    os=OSEnum.OS_LINUX.value,
                )
            )
            _LOG.debug(f'Saving formatted item: {formatted_item}')
            self.save_report(
                reports_dir=reports_dir,
                customer=customer,
                cloud=cloud,
                tenant=tenant,
                region=region,
                item=formatted_item
            )

    def dump_autoscaling_failed_resources(
            self, instance_type_mapping: dict,
            failed_resources: Dict[str, Exception],
            instance_meta_mapping: dict,
            id_file_mapping: dict,
            reports_dir: str,
    ):
        id_type_mapping = {}
        for instance_type, resources in instance_type_mapping.items():
            for instance_id in resources:
                id_type_mapping[instance_id] = instance_type

        _LOG.warning(f'Failed resources for auto scaling group: '
                     f'{list(failed_resources.keys())}. '
                     f'Dumping as ERROR recommendations')
        for instance_id, exception in failed_resources.items():
            customer, cloud, tenant, region, _, instance_id = self.parse_folders(
                metric_file_path=id_file_mapping.get(instance_id)
            )

            formatted_item = self.format_recommendation(
                stats=self.calculate_instance_stats(df=None,
                                                    exception=exception),
                instance_id=instance_id,
                general_action=ACTION_ERROR,
                meta=instance_meta_mapping.get(instance_id, {}),
                savings={}
            )
            _LOG.debug(f'Saving formatted item: {formatted_item}')
            self.save_report(
                reports_dir=reports_dir,
                customer=customer,
                cloud=cloud,
                tenant=tenant,
                region=region,
                item=formatted_item
            )

    def get_autoscaling_group_scale_action(self, dfs: List[pd.DataFrame],
                                           group_policy: dict,
                                           algorithm: Algorithm,
                                           instance_type: str):
        resource_loads = []

        for df in dfs:
            resource_load = self._get_load_percent(
                df=df
            )
            resource_loads.append(resource_load)

        current_group_load = sum(resource_loads) / len(resource_loads)

        thresholds = self._get_autoscaling_thresholds(
            group_policy=group_policy,
            algorithm=algorithm
        )
        action = ACTION_EMPTY
        if current_group_load <= thresholds[0]:
            action = ACTION_SCALE_DOWN
        elif current_group_load >= thresholds[2]:
            action = ACTION_SCALE_UP

        if action == ACTION_EMPTY:
            return action, 0

        scale_step = self._get_autoscaling_scale_step(
            group_policy=group_policy,
            instance_type=instance_type,
            resource_loads=resource_loads,
            thresholds=thresholds
        )
        return action, scale_step

    @staticmethod
    def _get_load_percent(df: pd.DataFrame, metrics=AUTOSCALING_METRICS):
        values = []
        for metric in metrics:
            if metric not in df.columns:
                continue
            if any([value not in (0, -1) for value in df[metric]]):
                values.append(df[metric].quantile(0.9))
        if not values:
            return 0
        return sum(values) / len(values)

    @staticmethod
    def _get_autoscaling_thresholds(group_policy: dict,
                                    algorithm: Algorithm):
        thresholds = group_policy.get(THRESHOLDS_ATTR)
        if thresholds:
            return (
                thresholds.get(MIN_ATTR),
                thresholds.get(DESIRED_ATTR),
                thresholds.get(MAX_ATTR),
            )
        algorithm_thresholds = algorithm.recommendation_settings.thresholds

        min_load = algorithm_thresholds[1]
        max_load = algorithm_thresholds[2]
        desired_load = round((min_load + max_load) / 2)

        return min_load, desired_load, max_load

    def _get_autoscaling_scale_step(self, group_policy: dict,
                                    thresholds: tuple,
                                    instance_type: str,
                                    resource_loads: List[float]):
        scale_step = group_policy.get(SCALE_STEP_ATTR)

        if isinstance(scale_step, int):
            return scale_step

        shape = self.shape_service.get(name=instance_type)

        shape_cpu = shape.cpu
        shape_ram = shape.memory

        total_used_cpu = 0
        total_used_ram = 0

        for resource_load in resource_loads:
            total_used_cpu += resource_load * shape_cpu / 100
            total_used_ram += resource_load * shape_ram / 100

        desired_load = thresholds[1]

        unused_koef = round(100 / desired_load, 2)

        required_cpu = total_used_cpu * unused_koef
        required_ram = total_used_ram * unused_koef

        required_instances_by_cpu = required_cpu / shape_cpu
        required_instances_by_ram = required_ram / shape_ram

        desired_instances_count = round((required_instances_by_cpu +
                                         required_instances_by_ram) / 2)
        return abs(len(resource_loads) - desired_instances_count)

    @staticmethod
    def _cooldown_period_passed(last_scan_date, cooldown_days):
        threshold_date = last_scan_date + timedelta(days=cooldown_days)
        return datetime.utcnow() >= threshold_date

    @staticmethod
    def _filter_outdated_resources(target_resources: List[str],
                                   dfs: Dict[str, pd.DataFrame]):
        last_df_dates = [dfs[resource_id].index.max().date()
                         for resource_id in target_resources]
        last_captured_date = max(last_df_dates)

        return [resource for resource in target_resources
                if dfs[resource].index.max().date() >= last_captured_date]
