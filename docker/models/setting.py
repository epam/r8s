from mongoengine import StringField, DynamicField

from models.base_model import BaseModel


class Setting(BaseModel):
    name = StringField(required=True, null=False)
    value = DynamicField(null=True)
