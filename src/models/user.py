from mongoengine import StringField, ListField

from models.base_model import BaseModel


class User(BaseModel):
    dto_skip_attrs = ['_id', 'password', 'latest_rt_version']

    user_id = StringField(required=True, unique=True)
    sub = StringField(unique=True)
    customer = StringField(null=True)
    roles = ListField(StringField(), default=list)
    password = StringField(null=True)
    latest_login = StringField(null=True)
    latest_rt_version = StringField(null=True)
    tenants = ListField(StringField(), default=list)
