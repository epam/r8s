import datetime

from mongoengine import StringField, DateTimeField, FloatField, \
    ListField, DictField, EnumField

from commons.enum import ListEnum
from models.base_model import BaseModel

RESOURCE_TYPE_INSTANCE = 'INSTANCE'
RESOURCE_TYPE_GROUP = 'GROUP'


class FeedbackStatusEnum(ListEnum):
    APPLIED = 'APPLIED'
    DONT_RECOMMEND = 'DONT_RECOMMEND'
    NO_ANSWER = 'NO_ANSWER'
    WRONG = 'WRONG'
    TOO_LARGE = 'TOO_LARGE'
    TOO_SMALL = 'TOO_SMALL'
    TOO_SHORT = 'TOO_SHORT'
    TOO_LONG = 'TOO_LONG'

    @classmethod
    def common(cls):
        return [cls.APPLIED, cls.DONT_RECOMMEND, cls.NO_ANSWER, cls.WRONG]

    @classmethod
    def resize(cls):
        return [cls.TOO_LARGE, cls.TOO_SMALL]

    @classmethod
    def schedule(cls):
        return [cls.TOO_LONG, cls.TOO_SHORT]


class RecommendationTypeEnum(ListEnum):
    ACTION_SCHEDULE = 'SCHEDULE'
    ACTION_SHUTDOWN = 'SHUTDOWN'
    ACTION_SCALE_UP = 'SCALE_UP'
    ACTION_SCALE_DOWN = 'SCALE_DOWN'
    ACTION_CHANGE_SHAPE = 'CHANGE_SHAPE'
    ACTION_SPLIT = 'SPLIT'
    ACTION_EMPTY = 'NO_ACTION'

    @classmethod
    def resize(cls):
        return [cls.ACTION_CHANGE_SHAPE,
                cls.ACTION_SCALE_UP,
                cls.ACTION_SCALE_DOWN,
                cls.ACTION_SPLIT]


class RecommendationHistory(BaseModel):
    resource_id = StringField(null=True)
    resource_type = StringField(null=True)
    job_id = StringField(null=True)
    customer = StringField(null=True)
    tenant = StringField(null=True)
    region = StringField(null=True)
    added_at = DateTimeField(null=False, default=datetime.datetime.utcnow)
    current_instance_type = StringField(null=True)
    current_month_price_usd = FloatField(null=True)
    recommendation_type = EnumField(RecommendationTypeEnum, null=True)
    recommendation = ListField(null=True, field=DictField(null=True))
    savings = ListField(field=DictField(null=True))
    instance_meta = DictField(null=True)
    feedback_dt = DateTimeField(null=True)
    feedback_status = EnumField(FeedbackStatusEnum, null=True)
    last_metric_capture_date = DateTimeField(null=True)

    meta = {
        'indexes': [
            'resource_id',
            'customer',
            ('resource_id', 'job_id'),
            {
                'fields': ['resource_id', 'added_at', 'recommendation_type'],
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
