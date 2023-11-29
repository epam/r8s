import datetime

from mongoengine import StringField, DateTimeField, EnumField, DictField

from commons.enum import ListEnum
from models.base_model import BaseModel


class JobStatusEnum(ListEnum):
    JOB_STARTED_STATUS = 'STARTED'
    JOB_RUNNABLE_STATUS = 'RUNNABLE'
    JOB_RUNNING_STATUS = 'RUNNING'
    JOB_SUCCEEDED_STATUS = 'SUCCEEDED'
    JOB_FAILED_STATUS = 'FAILED'


class JobTenantStatusEnum(ListEnum):
    TENANT_FORBIDDEN_STATUS = 'FORBIDDEN'
    TENANT_RUNNABLE_STATUS = 'RUNNABLE'
    TENANT_SUCCEEDED_STATUS = 'SUCCEEDED'
    TENANT_FAILED_STATUS = 'FAILED'


class Job(BaseModel):
    id = StringField(primary_key=True)
    name = StringField(unique=True)
    owner = StringField(null=True)
    job_queue = StringField(null=True)
    application_id = StringField(null=True)
    parent_id = StringField(null=True)
    created_at = DateTimeField(null=True)
    started_at = DateTimeField(null=True)
    stopped_at = DateTimeField(null=True)
    submitted_at = DateTimeField(null=True)
    status = EnumField(JobStatusEnum,
                       default=JobStatusEnum.JOB_RUNNABLE_STATUS)
    fail_reason = StringField(null=True)
    tenant_status_map = DictField(null=True)

    def get_dto(self):
        json_obj = self.get_json()
        json_obj['_id'] = str(json_obj.pop('_id'))

        for attr in self.dto_skip_attrs:
            json_obj.pop(attr, None)

        for attr, value in json_obj.items():
            if isinstance(value, datetime.datetime):
                json_obj[attr] = value.isoformat()
        return json_obj
