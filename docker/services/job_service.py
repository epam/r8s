from datetime import datetime

from mongoengine import DoesNotExist, ValidationError

from commons.log_helper import get_logger
from models.job import Job, JobStatusEnum
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-job-service')


class JobService:
    def __init__(self, environment_service: EnvironmentService):
        self.environment_service = environment_service

    @staticmethod
    def list():
        return list(Job.objects.all())

    @staticmethod
    def get_by_id(object_id):
        try:
            return Job.objects.get(id=object_id)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def get_by_name(name: str):
        try:
            return Job.objects.get(name=name)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def _save(job: Job):
        job.save()

    @staticmethod
    def _delete(job: Job):
        job.delete()

    def set_status(self, job: Job, status):
        if status not in JobStatusEnum.list():
            return
        job.status = status
        if status == JobStatusEnum.JOB_RUNNING_STATUS.value:
            job.created_at = datetime.utcnow()
        end_states = (JobStatusEnum.JOB_SUCCEEDED_STATUS.value,
                      JobStatusEnum.JOB_FAILED_STATUS.value)
        if status in end_states:
            job.stopped_at = datetime.utcnow()
        self._save(job=job)
        return job
