from typing import List
import datetime

from commons.constants import ACTION_EMPTY, ACTION_ERROR, ACTION_SCHEDULE, \
    ACTION_SCALE_UP, ACTION_SCALE_DOWN, ACTION_CHANGE_SHAPE, ACTION_SPLIT, \
    ACTION_SHUTDOWN
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory, \
    FeedbackStatusEnum, RecommendationTypeEnum

_LOG = get_logger('r8s-recommendation-history-service')

RESIZE_ACTIONS = [ACTION_SCALE_UP, ACTION_SCALE_DOWN,
                  ACTION_CHANGE_SHAPE, ACTION_SPLIT]


class RecommendationHistoryService:

    def create(self, instance_id: str, job_id: str, customer: str, tenant: str,
               region: str, current_instance_type: str, savings: dict,
               schedule: list,
               recommended_shapes: list,
               actions: list,
               instance_meta: dict) -> List[RecommendationHistory]:
        if ACTION_EMPTY in actions or ACTION_ERROR in actions:
            _LOG.debug(f'Skipping saving result to history collection. '
                       f'Actions: \'{actions}\'')
            return []
        result = []
        current_month_price_usd = self._get_current_month_price(
            savings=savings
        )
        if ACTION_SCHEDULE in actions:
            schedule_savings = self._filter_savings_usd(
                savings=savings,
                action=ACTION_SCHEDULE
            )
            recommendation_item = self._create_or_update_recent(
                instance_id=instance_id,
                job_id=job_id,
                customer=customer,
                tenant=tenant,
                region=region,
                current_instance_type=current_instance_type,
                current_month_price_usd=current_month_price_usd,
                recommendation_type=ACTION_SCHEDULE,
                recommendation=schedule,
                savings=schedule_savings,
                instance_meta=instance_meta
            )
            result.append(recommendation_item)

        resize_action = self._get_resize_action(actions=actions)
        if resize_action:
            resize_savings = self._filter_savings_usd(
                savings=savings,
                action=resize_action
            )
            recommendation_item = self._create_or_update_recent(
                instance_id=instance_id,
                job_id=job_id,
                customer=customer,
                tenant=tenant,
                region=region,
                current_instance_type=current_instance_type,
                current_month_price_usd=current_month_price_usd,
                recommendation_type=resize_action,
                recommendation=recommended_shapes,
                savings=resize_savings,
                instance_meta=instance_meta
            )
            result.append(recommendation_item)
        if ACTION_SHUTDOWN in actions:
            shutdown_savings = self._filter_savings_usd(
                savings=savings,
                action=ACTION_SHUTDOWN
            )
            recommendation_item = self._create_or_update_recent(
                instance_id=instance_id,
                job_id=job_id,
                customer=customer,
                tenant=tenant,
                region=region,
                current_instance_type=current_instance_type,
                current_month_price_usd=current_month_price_usd,
                recommendation_type=ACTION_SHUTDOWN,
                recommendation=None,
                savings=shutdown_savings,
                instance_meta=instance_meta
            )
            result.append(recommendation_item)
        return result

    def _create_or_update_recent(self, instance_id, job_id, customer, tenant,
                                 region, current_instance_type,
                                 current_month_price_usd, recommendation_type,
                                 recommendation, savings, instance_meta):
        recent_recommendations = self.get_recent_recommendation(
            instance_id=instance_id,
            recommendation_type=recommendation_type,
            without_feedback=True
        )
        if recommendation is not None and not isinstance(recommendation, list):
            recommendation = [recommendation]

        if not recent_recommendations:
            _LOG.debug(f'No recent \'{recommendation_type}\' recommendation '
                       f'found for instance \'{instance_id}\'. Creating new '
                       f'record.')
            return RecommendationHistory(
                instance_id=instance_id,
                job_id=job_id,
                customer=customer,
                tenant=tenant,
                region=region,
                current_instance_type=current_instance_type,
                current_month_price_usd=current_month_price_usd,
                recommendation_type=recommendation_type,
                recommendation=recommendation,
                savings=savings,
                instance_meta=instance_meta
            )
        recent_recommendations = list(recent_recommendations)
        if len(recent_recommendations) > 1:
            _LOG.error(f'More than one recent recommendation found. '
                       f'Deleting all except the most recent')
            for recommendation in recent_recommendations[1:]:
                self.delete(recommendation=recommendation)

        recent_recommendation: RecommendationHistory = recent_recommendations[0]
        _LOG.debug(f'Recent recommendation found, updating.')
        recent_recommendation.update(
            job_id=job_id,
            customer=customer,
            tenant=tenant,
            region=region,
            added_at=datetime.datetime.utcnow(),
            current_instance_type=current_instance_type,
            current_month_price_usd=current_month_price_usd,
            recommendation=recommendation,
            savings=savings,
            instance_meta=instance_meta
        )
        return recent_recommendation

    def get_recent_recommendation(self, instance_id, recommendation_type,
                                  without_feedback=False):
        threshold_date = self._get_week_start_dt()

        query = {
            'instance_id': instance_id,
            'recommendation_type': recommendation_type,
            'added_at__gt': threshold_date
        }
        if without_feedback:
            query['feedback_dt'] = None
            query['feedback_status'] = None

        return RecommendationHistory.objects(**query).order_by('-added_at')

    @staticmethod
    def get_recommendation_with_feedback(instance_id):
        return list(RecommendationHistory.objects(
            instance_id=instance_id,
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
    def _get_resize_action(actions):
        for action in actions:
            if action in RESIZE_ACTIONS:
                return action

    @staticmethod
    def _filter_savings_usd(savings: dict, action):
        if not savings:
            return
        saving_options = savings.get('saving_options', [])
        if not saving_options:
            return
        option_savings_usd = [option.get('saving_month_usd') for
                              option in saving_options
                              if option.get('action') == action]
        return [saving for saving in option_savings_usd
                if isinstance(saving, (int, float))]

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
