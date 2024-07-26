from datetime import datetime, timedelta, timezone

from commons.constants import CUSTOMER_ATTR, INSTANCE_ID_ATTR, ADDED_AT_ATTR, \
    RECOMMENDATION_TYPE_ATTR, JOB_ID_ATTR, TENANT_ATTR, RESOURCE_ID_ATTR, \
    RESOURCE_TYPE_ATTR
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory, \
    RESOURCE_TYPE_INSTANCE

_LOG = get_logger('r8s-recommendation-history-service')


class RecommendationHistoryService:
    def get_recent_recommendation(self, resource_id, recommendation_type,
                                  customer=None, limit=None):
        threshold_date = self._get_week_start_dt()
        query = {
            'resource_id': resource_id,
            'recommendation_type': recommendation_type,
            'added_at__gt': threshold_date
        }
        if customer:
            query['customer'] = customer

        query_set = RecommendationHistory.objects(**query) \
            .order_by('-added_at')

        if limit:
            query_set = query_set.limit(limit)
        return query_set

    @staticmethod
    def list(customer: str = None, tenant: str = None,
             resource_id: str = None,
             resource_type: str = RESOURCE_TYPE_INSTANCE,
             job_id: str = None, from_dt: datetime = None,
             to_dt: datetime = None,
             recommendation_type: str = None):
        query_params = {
            CUSTOMER_ATTR: customer,
            TENANT_ATTR: tenant,
            RESOURCE_ID_ATTR: resource_id,
            RESOURCE_TYPE_ATTR: resource_type,
            JOB_ID_ATTR: job_id,
            f'{ADDED_AT_ATTR}__gt': from_dt,
            f'{ADDED_AT_ATTR}__lt': to_dt,
            RECOMMENDATION_TYPE_ATTR: recommendation_type,
        }
        query_params = {k: v for k, v in query_params.items() if v is not None}
        return RecommendationHistory.objects(**query_params)

    def save_feedback(self, recommendation: RecommendationHistory,
                      feedback_status: str = None):
        recommendation.feedback_status = feedback_status
        recommendation.feedback_dt = datetime.now(timezone.utc)
        self.save(recommendation=recommendation)
        return recommendation

    @staticmethod
    def save(recommendation: RecommendationHistory):
        recommendation.save()

    @staticmethod
    def delete(recommendation: RecommendationHistory):
        recommendation.delete()

    @staticmethod
    def _get_week_start_dt():
        now = datetime.now(timezone.utc)
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now - timedelta(days=now.weekday())
