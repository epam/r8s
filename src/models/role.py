from mongoengine import StringField, ListField, DateTimeField

from models.base_model import BaseModel


class Role(BaseModel):
    name = StringField(hash_key=True, required=True, unique=True)
    expiration = DateTimeField(null=True)
    policies = ListField(StringField(null=True))
    resource = ListField(StringField(null=True))

    def get_dto(self):
        json_obj = self.get_json()
        json_obj['_id'] = str(json_obj.pop('_id'))

        for attr in self.dto_skip_attrs:
            json_obj.pop(attr, None)

        json_obj['expiration'] = json_obj['expiration'].isoformat()
        return json_obj
