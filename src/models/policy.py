from mongoengine import StringField, ListField

from models.base_model import BaseModel

EFFECT_ALLOW = 'allow'
EFFECT_DENY = 'deny'


class Policy(BaseModel):
    name = StringField(max_length=30, required=True, unique=True)
    permissions = ListField(StringField(null=True))
    customer = StringField(null=True)
    effect = StringField(choices=[EFFECT_ALLOW, EFFECT_DENY],
                         default=EFFECT_ALLOW)
    tenants = ListField(StringField())
