import datetime

from mongoengine import StringField, FloatField, EnumField, DateTimeField

from models.base_model import BaseModel, CloudEnum


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
