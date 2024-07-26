from mongoengine import StringField, BinaryField

from models.base_model import BaseModel


class User(BaseModel):
    user_id = StringField(hash_key=True)
    sub = StringField(unique=True)
    customer = StringField(null=True)
    role = StringField(null=True)
    password = StringField(null=True)
    latest_login = StringField(null=True)
