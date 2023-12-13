import json
import os
from datetime import datetime
from typing import Union, List
import itertools

import numpy as np
import pandas as pd

from commons.constants import STATUS_ERROR, STATUS_OK, OK_MESSAGE, \
    ACTION_SHUTDOWN, ACTION_SCHEDULE, ACTION_SPLIT, ACTION_EMPTY, \
    STATUS_POSTPONED, CURRENT_INSTANCE_TYPE_ATTR, CURRENT_MONTHLY_PRICE_ATTR, \
    SAVING_OPTIONS_ATTR
from commons.exception import ExecutorException, ProcessingPostponedException
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.algorithm import Algorithm
from models.base_model import CloudEnum
from models.parent_attributes import LicensesParentMeta
from models.recommendation_history import RecommendationHistory, \
    RecommendationTypeEnum
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

_LOG = get_logger('r8s-recommendation-service')

RIGHTSIZER_SOURCE = 'RIGHTSIZER'
RIGHTSIZER_RESOURCE_TYPE = 'INSTANCE'
DEFAULT_SEVERITY = 'MEDIUM'


class RecommendationService:
    def __init__(self, metrics_service: MetricsService,
                 schedule_service: ScheduleService,
                 resize_service: ResizeService,
                 environment_service: EnvironmentService,
                 saving_service: SavingService,
                 meta_service: MetaService,
                 recommendation_history_service: RecommendationHistoryService):
        self.metrics_service = metrics_service
        self.schedule_service = schedule_service
        self.resize_service = resize_service
        self.environment_service = environment_service
        self.saving_service = saving_service
        self.meta_service = meta_service
        self.recommendation_history_service = recommendation_history_service

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
        savings = {}
        advanced = None

        customer, cloud, tenant, region, _, instance_id = self._parse_folders(
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

        _LOG.debug(f'Loading past recommendation with feedback')
        past_recommendations_feedback = self.recommendation_history_service. \
            get_recommendation_with_feedback(instance_id=instance_id)

        applied_recommendations = self.recommendation_history_service. \
            filter_applied(recommendations=past_recommendations_feedback)
        try:
            _LOG.debug(f'Loading adjustments from meta')
            meta_adjustments = self.meta_service.to_adjustments(
                instance_meta=instance_meta
            )
            applied_recommendations.extend(meta_adjustments)
            _LOG.debug(f'Loading df')
            df = self.metrics_service.load_df(
                path=metric_file_path,
                algorithm=algorithm,
                applied_recommendations=applied_recommendations,
                instance_meta=instance_meta
            )

            _LOG.debug(f'Extracting instance type name')
            instance_type = self.metrics_service.get_instance_type(
                metric_file_path=metric_file_path,
                algorithm=algorithm
            )
            _LOG.debug(f'Dividing into periods with different load')
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
            if non_straight_periods and total_length:
                _LOG.debug(f'Calculating resize trends for several loads')
                trends = self.metrics_service. \
                    calculate_instance_trend_multiple(
                    algorithm=algorithm,
                    non_straight_periods=non_straight_periods,
                    total_length=total_length
                )
            else:
                _LOG.debug(f'Generating resize trend')
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
            else:
                schedule = self.schedule_service.generate_schedule(
                    shutdown_periods=shutdown_periods,
                    recommendation_settings=algorithm.recommendation_settings,
                    instance_id=instance_id,
                    df=df,
                    instance_meta=instance_meta,
                    past_recommendations=applied_recommendations
                )
            _LOG.debug(f'Searching for resize action')
            resize_action = ResizeTrend.get_resize_action(trends=trends)

            _LOG.debug(f'Searching for better-fix instance types')
            compatibility_rule = algorithm.recommendation_settings. \
                shape_compatibility_rule

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
                past_recommendations=past_recommendations_feedback
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
                    instance_id=instance_id,
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
                if history_items:
                    _LOG.debug(
                        f'Saving \'{len(history_items)}\' history items')
                    self.recommendation_history_service.batch_save(
                        recommendations=history_items)
            except Exception as e:
                _LOG.error(f'Exception occurred while saving recommendation '
                           f'to history: {str(e)}')
        except Exception as e:
            _LOG.debug(f'Calculate instance stats with exception')
            stats = self.calculate_instance_stats(df=df, exception=e)
            general_action = self.get_general_action(
                schedule=schedule,
                shapes=recommended_sizes,
                resize_action=resize_action,
                stats=stats)

        _LOG.debug(f'Dumping instance results')
        item = self.dump_reports(
            reports_dir=reports_dir,
            instance_id=instance_id,
            schedule=schedule,
            recommended_sizes=recommended_sizes,
            stats=stats,
            customer=customer,
            cloud=cloud,
            tenant=tenant,
            region=region,
            meta=instance_meta,
            general_action=general_action,
            savings=savings,
            advanced=advanced
        )
        return item

    def dump_error_report(self, reports_dir, metric_file_path,
                          exception):
        customer, cloud, tenant, region, _, instance_id = self._parse_folders(
            metric_file_path=metric_file_path
        )
        stats = self.calculate_instance_stats(exception=exception)
        return self.dump_reports(
            reports_dir=reports_dir,
            instance_id=instance_id,
            schedule=[],
            recommended_sizes=[],
            stats=stats,
            customer=customer,
            cloud=cloud,
            tenant=tenant,
            region=region,
            meta={},
            general_action=STATUS_ERROR
        )

    def dump_reports(self, reports_dir, customer, cloud, tenant, region, stats,
                     instance_id=None, schedule=None, recommended_sizes=None,
                     meta=None, general_action=None,
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

        dir_path = os.path.join(reports_dir, customer, cloud, tenant)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f'{region}.jsonl')

        with open(file_path, 'a') as f:
            f.write(json.dumps(item))
            f.write('\n')
        return item

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

        return self.dump_reports(
            reports_dir=reports_dir,
            customer=recommendations[0].customer,
            cloud=cloud,
            tenant=recommendations[0].tenant,
            region=recommendations[0].region,
            instance_id=recommendations[0].instance_id,
            stats=stats,
            schedule=schedule,
            recommended_sizes=recommended_sizes,
            meta=recommendations[0].instance_meta,
            general_action=actions,
            savings=savings
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
        _LOG.debug(f'Calculating advanced stats')
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

        _LOG.debug(f'Calculating clustering stats')
        cluster_stats = self._get_clusters_stats(centroids=centroids)
        _LOG.debug(f'Clustering stats: {cluster_stats}')
        result['clusters'] = cluster_stats

        return result

    @staticmethod
    def _parse_folders(metric_file_path):
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

    def get_general_action(self, schedule, shapes, stats, resize_action,
                           past_recommendations: list = None):
        actions = []
        status = stats.get('status', '')
        if status == STATUS_POSTPONED:
            return [ACTION_EMPTY]
        if status != STATUS_OK:
            return [STATUS_ERROR]

        shutdown_forbidden = False
        if past_recommendations:
            shutdown_forbidden = self.recommendation_history_service. \
                is_shutdown_forbidden(
                recommendations=past_recommendations
            )

        if not schedule and not shutdown_forbidden:
            return [ACTION_SHUTDOWN]

        if schedule and not self._is_schedule_always_run(schedule=schedule):
            actions.append(ACTION_SCHEDULE)

        if shapes:
            shape = shapes[0]
            if 'probability' in shape:
                actions.append(ACTION_SPLIT)
            else:
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
