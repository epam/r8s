from mongoengine import StringField, ListField

from models.base_model import BaseModel


class Policy(BaseModel):
    name = StringField(max_length=30, required=True, unique=True)
    permissions = ListField(StringField(null=True))
