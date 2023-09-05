from mongoengine import Document

from commons.enum import ListEnum


class CloudEnum(ListEnum):
    CLOUD_AWS = 'AWS'
    CLOUD_AZURE = 'AZURE'
    CLOUD_GOOGLE = 'GOOGLE'


class BaseModel(Document):
    meta = {'abstract': True}
    dto_skip_attrs = []

    def get_json(self):
        return self.to_mongo().to_dict()

    def get_dto(self):
        json_obj = self.get_json()
        json_obj['_id'] = str(json_obj.pop('_id'))

        for attr in self.dto_skip_attrs:
            json_obj.pop(attr, None)
        return json_obj
