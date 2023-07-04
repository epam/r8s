from mongoengine import EnumField, DictField, StringField, EmbeddedDocument, \
    EmbeddedDocumentField

from commons.enum import ListEnum
from models.base_model import BaseModel


class StorageServiceEnum(ListEnum):
    S3_BUCKET = 'S3_BUCKET'

    @classmethod
    def get_default(cls):
        return cls.S3_BUCKET


class StorageTypeEnum(ListEnum):
    DATA_SOURCE = 'DATA_SOURCE'
    STORAGE = 'STORAGE'


class Storage(BaseModel):
    name = StringField(unique=True)
    service = EnumField(StorageServiceEnum)
    type = EnumField(StorageTypeEnum)
    access = DictField()

    meta = {'allow_inheritance': True}
    dto_skip_attrs = ['_cls']


class S3Access(EmbeddedDocument):
    bucket_name = StringField()
    prefix = StringField(null=True)


class S3Storage(Storage):
    name = StringField(unique=True)
    service = EnumField(StorageServiceEnum)
    type = EnumField(StorageTypeEnum)
    access = EmbeddedDocumentField(S3Access)

    dto_skip_attrs = ['_cls']
