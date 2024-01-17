from mongoengine import StringField, DictField, EmbeddedDocument, IntField, \
    EmbeddedDocumentField

from models.base_model import BaseModel

PERMITTED_ATTACHMENT = 'permitted'
PROHIBITED_ATTACHMENT = 'prohibited'
ALLOWED_ATTACHMENT_MODELS = (PERMITTED_ATTACHMENT, PERMITTED_ATTACHMENT)


class AllowanceAttribute(EmbeddedDocument):
    time_range = StringField(null=True)
    job_balance = IntField(null=True)
    balance_exhaustion_model = StringField(null=True)


class License(BaseModel):
    license_key = StringField(unique=True)
    customers = DictField(null=True)
    expiration = StringField(null=True)  # ISO8601
    algorithm_mapping = DictField(null=True)
    latest_sync = StringField(null=True)  # ISO8601
    allowance = EmbeddedDocumentField(AllowanceAttribute, null=True)
