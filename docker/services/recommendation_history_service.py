from typing import List, Dict, Optional
import datetime

from commons.constants import ACTION_EMPTY, ACTION_ERROR, ACTION_SCHEDULE, \
    ACTION_SCALE_UP, ACTION_SCALE_DOWN, ACTION_CHANGE_SHAPE, ACTION_SPLIT, \
    ACTION_SHUTDOWN, SAVING_OPTIONS_ATTR
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory, \
    FeedbackStatusEnum, RecommendationTypeEnum, RESOURCE_TYPE_INSTANCE, \
    RESOURCE_TYPE_GROUP

_LOG = get_logger('r8s-recommendation-history-service')

RESIZE_ACTIONS = [ACTION_SCALE_UP, ACTION_SCALE_DOWN,
                  ACTION_CHANGE_SHAPE, ACTION_SPLIT]


class RecommendationHistoryService:

    def create(self, resource_id: str,
               job_id: str, customer: str, tenant: str,
               region: str, current_instance_type: str, savings: dict,
               schedule: list, recommended_shapes: list, actions: list,
               instance_meta: dict,
               last_metric_capture_date: datetime.date,
               resource_type=RESOURCE_TYPE_INSTANCE
               ) -> List[RecommendationHistory]:
        if ACTION_ERROR in actions:
            _LOG.debug(f'Skipping saving result to history collection. '
                       f'Actions: \'{actions}\'')
            return []
        result = []
        current_month_price_usd = self._get_current_month_price(
            savings=savings
        )
        saving_options = savings.get(SAVING_OPTIONS_ATTR, [])

        for action in actions:
            recommendation = None
            if action in [*RESIZE_ACTIONS, ACTION_EMPTY, ACTION_SHUTDOWN]:
                recommendation = recommended_shapes
            elif action == ACTION_SCHEDULE:
                recommendation = schedule

            if recommendation is None:
                _LOG.warning(f'Unknown recommendation type detected: '
                             f'{action}')
                continue
            recommendation_item = self._create_or_update_recent(
                resource_id=resource_id,
                resource_type=resource_type,
                job_id=job_id,
                customer=customer,
                tenant=tenant,
                region=region,
                current_instance_type=current_instance_type,
                current_month_price_usd=current_month_price_usd,
                recommendation_type=action,
                recommendation=recommendation,
                savings=saving_options,
                instance_meta=instance_meta,
                last_metric_capture_date=last_metric_capture_date
            )
            result.append(recommendation_item)
        return result

    def create_group_recommendation(self, resource_id: str,
                                    job_id: str, customer: str, tenant: str,
                                    region: str, current_instance_type: str,
                                    action: str, recommendation: dict,
                                    instance_meta: dict,
                                    last_metric_capture_date: datetime.date
                                    ) -> Optional[RecommendationHistory]:
        if action == ACTION_ERROR:
            _LOG.debug(f'Skipping saving result to history collection. '
                       f'Action: \'{action}\'')
            return
        return self._create_or_update_recent(
            resource_id=resource_id,
            resource_type=RESOURCE_TYPE_GROUP,
            job_id=job_id,
            customer=customer,
            tenant=tenant,
            region=region,
            current_instance_type=current_instance_type,
            current_month_price_usd=None,
            recommendation_type=action,
            recommendation=recommendation,
            savings=None,
            instance_meta=instance_meta,
            last_metric_capture_date=last_metric_capture_date
        )

    def _create_or_update_recent(self, resource_id, resource_type,
                                 job_id, customer, tenant,
                                 region, current_instance_type,
                                 current_month_price_usd, recommendation_type,
                                 recommendation, savings, instance_meta,
                                 last_metric_capture_date):
        recent_recommendations = self.get_recent_recommendation(
            resource_id=resource_id,
            resource_type=resource_type,
            recommendation_type=recommendation_type,
            without_feedback=True
        )
        if recommendation is not None and not isinstance(recommendation, list):
            recommendation = [recommendation]

        if not recent_recommendations:
            _LOG.debug(f'No recent \'{recommendation_type}\' recommendation '
                       f'found for resource \'{resource_id}\'. Creating new '
                       f'record.')
            return RecommendationHistory(
                resource_id=resource_id,
                resource_type=resource_type,
                job_id=job_id,
                customer=customer,
                tenant=tenant,
                region=region,
                current_instance_type=current_instance_type,
                current_month_price_usd=current_month_price_usd,
                recommendation_type=recommendation_type,
                recommendation=recommendation,
                savings=savings,
                instance_meta=instance_meta,
                last_metric_capture_date=last_metric_capture_date
            )
        recent_recommendations = list(recent_recommendations)
        if len(recent_recommendations) > 1:
            _LOG.error('More than one recent recommendation found. '
                       'Deleting all except the most recent')
            for recommendation in recent_recommendations[1:]:
                self.delete(recommendation=recommendation)

        recent_recommendation: RecommendationHistory = recent_recommendations[0]
        _LOG.debug('Recent recommendation found, updating.')
        recent_recommendation.update(
            job_id=job_id,
            customer=customer,
            tenant=tenant,
            region=region,
            added_at=datetime.datetime.utcnow(),
            current_instance_type=current_instance_type,
            current_month_price_usd=current_month_price_usd,
            recommendation=recommendation,
            recommendation_type=recommendation_type,
            savings=savings,
            instance_meta=instance_meta,
            last_metric_capture_date=last_metric_capture_date
        )
        return recent_recommendation

    def get_recent_recommendation(self, resource_id,
                                  resource_type=RESOURCE_TYPE_INSTANCE,
                                  recommendation_type=None,
                                  without_feedback=False, limit=None):
        threshold_date = self._get_week_start_dt()

        query = {
            'resource_id': resource_id,
            'resource_type': resource_type,
            'added_at__gt': threshold_date
        }
        if recommendation_type:
            query['recommendation_type']: recommendation_type
        if without_feedback:
            query['feedback_dt'] = None
            query['feedback_status'] = None

        result = RecommendationHistory.objects(**query).order_by('-added_at')
        if limit:
            result = result.limit(limit)
        return result

    def get_tenant_recommendation(
            self, tenant: str, last_days=60,
            filter_only_last_job=True,
            resource_type: str = RESOURCE_TYPE_INSTANCE) -> \
            Dict[str, List[RecommendationHistory]]:
        threshold_date = self._get_past_date(n_days=last_days)
        query = {
            'added_at__gt': threshold_date,
            'tenant': tenant,
            'resource_type': resource_type
        }
        items = RecommendationHistory.objects(**query).order_by('-added_at')
        result = {}

        for item in items:
            instance_id = item.resource_id
            if instance_id not in result:
                result[instance_id] = [item]
            elif (not filter_only_last_job or
                  result[instance_id][0].job_id == item.job_id):
                result[instance_id].append(item)

        return result

    def get_instance_last_captured_date_map(
            self, tenant, resource_type=RESOURCE_TYPE_INSTANCE, last_days=40):
        threshold_date = self._get_past_date(n_days=last_days)
        query = {
            'added_at__gt': threshold_date,
            'tenant': tenant,
            'resource_type': resource_type
        }
        items = RecommendationHistory.objects(**query).order_by('-added_at')

        result = {}
        for item in items:
            instance_id = item.resource_id
            last_captured_date = item.last_metric_capture_date

            if (instance_id not in result or
                    result[instance_id] < last_captured_date):
                result[instance_id] = last_captured_date
        return result

    @staticmethod
    def get_instance_recommendations(instance_id, limit=None):
        query = {
            'resource_id': instance_id,
            'resource_type': "INSTANCE"
        }

        result = RecommendationHistory.objects(**query).order_by('-added_at')
        if limit:
            result = result.limit(limit)
        return result

    @staticmethod
    def get_recommendation_with_feedback(instance_id):
        return list(RecommendationHistory.objects(
            resource_id=instance_id,
            resource_type=RESOURCE_TYPE_INSTANCE,
            feedback_dt__ne=None,
            feedback_status__ne=None
        ))

    @staticmethod
    def filter_applied(recommendations: List[RecommendationHistory]):
        return [item for item in recommendations if
                item.feedback_status == FeedbackStatusEnum.APPLIED]

    @staticmethod
    def filter_resize(recommendations: List[RecommendationHistory]):
        allowed_recommendation_types = RecommendationTypeEnum.resize()
        return [item for item in recommendations if
                item.recommendation_type in allowed_recommendation_types]

    @staticmethod
    def is_shutdown_forbidden(recommendations: List[RecommendationHistory]):
        for recommendation in recommendations:
            if recommendation.recommendation_type != \
                    RecommendationTypeEnum.ACTION_SHUTDOWN:
                continue
            if recommendation.feedback_status not in \
                    (FeedbackStatusEnum.DONT_RECOMMEND,
                     FeedbackStatusEnum.WRONG):
                continue
            return True
        return False

    @staticmethod
    def batch_save(recommendations: List[RecommendationHistory]):
        to_update = []
        to_create = []
        for recommendation in recommendations:
            if recommendation.get_json().get('_id'):
                to_update.append(recommendation)
            else:
                to_create.append(recommendation)

        if to_create:
            RecommendationHistory.objects.insert(to_create)
        for recommendation in to_update:
            recommendation.save()

    @staticmethod
    def save(recommendation: RecommendationHistory):
        recommendation.save()

    @staticmethod
    def delete(recommendation: RecommendationHistory):
        recommendation.delete()

    @staticmethod
    def _get_current_month_price(savings: dict):
        if not savings:
            return
        return savings.get('current_monthly_price_usd')

    @staticmethod
    def _get_week_start_dt():
        now = datetime.datetime.now(datetime.timezone.utc)
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now - datetime.timedelta(days=now.weekday())

    @staticmethod
    def _get_past_date(n_days: int):
        now = datetime.datetime.now(datetime.timezone.utc)
        target = now - datetime.timedelta(days=n_days)
        return target.date()
