import datetime

from mongoengine import StringField, FloatField, EnumField, DateTimeField

from commons.enum import ListEnum
from models.base_model import BaseModel


class CloudEnum(ListEnum):
    CLOUD_AWS = 'AWS'
    CLOUD_AZURE = 'AZURE'
    CLOUD_GOOGLE = 'GOOGLE'


class Shape(BaseModel):
    dto_skip_attrs = ['_id', 'added_at']

    name = StringField(null=False, unique=True)
    cloud = EnumField(CloudEnum)

    cpu = FloatField(null=True)
    memory = FloatField(null=True)
    network_throughput = FloatField(null=True)
    iops = FloatField(null=True)

    family_type = StringField(null=True)
    physical_processor = StringField(null=True)
    architecture = StringField(null=True)
    added_at = DateTimeField(null=False, default=datetime.datetime.utcnow)
