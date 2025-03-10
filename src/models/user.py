from mongoengine import StringField

from models.base_model import BaseModel


class User(BaseModel):
    dto_skip_attrs = ['_id', 'password', 'latest_rt_version']

    user_id = StringField(hash_key=True)
    sub = StringField(unique=True)
    customer = StringField(null=True)
    role = StringField(null=True)
    password = StringField(null=True)
    latest_login = StringField(null=True)
    latest_rt_version = StringField(null=True)
