from datetime import datetime

from mongoengine import StringField, DateTimeField, FloatField, \
    ListField, DictField, EnumField

from commons.enum import ListEnum
from models.base_model import BaseModel


class FeedbackStatusEnum(ListEnum):
    APPLIED = 'APPLIED'
    DONT_RECOMMEND = 'DONT_RECOMMEND'
    NO_ANSWER = 'NO_ANSWER'
    WRONG = 'WRONG'
    TOO_LARGE = 'TOO_LARGE'
    TOO_SMALL = 'TOO_SMALL'
    TOO_SHORT = 'TOO_SHORT'
    TOO_LONG = 'TOO_LONG'


class RecommendationTypeEnum(ListEnum):
    ACTION_SCHEDULE = 'SCHEDULE'
    ACTION_SHUTDOWN = 'SHUTDOWN'
    ACTION_SCALE_UP = 'SCALE_UP'
    ACTION_SCALE_DOWN = 'SCALE_DOWN'
    ACTION_CHANGE_SHAPE = 'CHANGE_SHAPE'
    ACTION_SPLIT = 'SPLIT'

    @classmethod
    def get_allowed_feedback_types(cls, recommendation_type):
        options = [FeedbackStatusEnum.APPLIED,
                   FeedbackStatusEnum.DONT_RECOMMEND,
                   FeedbackStatusEnum.NO_ANSWER,
                   FeedbackStatusEnum.WRONG]
        if recommendation_type == cls.ACTION_SCHEDULE.value:
            options.extend([FeedbackStatusEnum.TOO_SHORT,
                            FeedbackStatusEnum.TOO_LONG])
        resize_actions = (cls.ACTION_SPLIT.value,
                          cls.ACTION_SCALE_UP.value,
                          cls.ACTION_SCALE_DOWN.value,
                          cls.ACTION_CHANGE_SHAPE.value)
        if recommendation_type in resize_actions:
            options.extend([FeedbackStatusEnum.TOO_LARGE,
                            FeedbackStatusEnum.TOO_SMALL])

        return [option.value for option in options]

    @classmethod
    def resize(cls):
        return [cls.ACTION_CHANGE_SHAPE,
                cls.ACTION_SCALE_UP,
                cls.ACTION_SCALE_DOWN,
                cls.ACTION_SPLIT]

class RecommendationHistory(BaseModel):
    instance_id = StringField(null=True)
    job_id = StringField(null=True)
    customer = StringField(null=True)
    tenant = StringField(null=True)
    region = StringField(null=True)
    added_at = DateTimeField(null=False, default=datetime.utcnow)
    current_instance_type = StringField(null=True)
    current_month_price_usd = FloatField(null=True)
    recommendation_type = EnumField(RecommendationTypeEnum, null=True)
    recommendation = ListField(null=True, field=DictField(null=True))
    savings = ListField(field=FloatField(null=True))
    instance_meta = DictField(null=True)
    feedback_dt = DateTimeField(null=True)
    feedback_status = EnumField(FeedbackStatusEnum, null=True)

    dto_skip_attrs = ['savings', 'instance_meta']
    meta = {
        'indexes': [
            'instance_id',
            'customer',
            ('instance_id', 'job_id'),
            {
                'fields': ['instance_id', 'added_at', 'recommendation_type'],
                'unique': True
            },
            {
                'fields': ['added_at'],
                'expireAfterSeconds': 3600 * 24 * 30 * 3  # 3 months
            },
        ],
        'auto_create_index': True,
        'auto_create_index_on_save': False,
    }

    def get_dto(self):
        recommendation_dto = super(RecommendationHistory, self).get_dto()
        added_at = recommendation_dto.get('added_at')
        if isinstance(added_at, datetime):
            recommendation_dto['added_at'] = added_at.isoformat()

        applied_at = recommendation_dto.get('feedback_dt')
        if isinstance(applied_at, datetime):
            recommendation_dto['feedback_dt'] = applied_at.isoformat()
        return recommendation_dto
