from mongoengine import StringField, FloatField, EnumField

from commons.enum import ListEnum
from models.base_model import BaseModel
from models.shape import CloudEnum

DEFAULT_CUSTOMER = 'DEFAULT'


class OSEnum(ListEnum):
    OS_WINDOWS = 'WINDOWS'
    OS_LINUX = 'LINUX'


class ShapePrice(BaseModel):
    dto_skip_attrs = ['_id']

    customer = StringField(null=False, default=DEFAULT_CUSTOMER)
    cloud = EnumField(CloudEnum)
    name = StringField(null=True)
    region = StringField(null=True)
    os = EnumField(OSEnum)
    on_demand = FloatField(null=True)
    reserved_1y = FloatField(null=True)
    reserved_3y = FloatField(null=True)
    dedicated = FloatField(null=True)

    meta = {
        'indexes': [
            {
                'fields': ('customer', 'name', 'region', 'os'),
                'unique': True
            }
        ],
        'auto_create_index': True,
        'auto_create_index_on_save': False,
    }
