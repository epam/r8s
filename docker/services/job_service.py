from datetime import datetime

from mongoengine import DoesNotExist, ValidationError

from commons.log_helper import get_logger
from commons.time_helper import utc_iso
from models.job import Job, JobStatusEnum
from services.environment_service import EnvironmentService
from services.license_manager_service import LicenseManagerService

_LOG = get_logger('r8s-job-service')


class JobService:
    def __init__(self, environment_service: EnvironmentService,
                 license_manager_service: LicenseManagerService):
        self.environment_service = environment_service
        self.license_manager_service = license_manager_service

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

    def set_status(self, job: Job, status: str, licensed_job_ids: list = None):
        if status not in JobStatusEnum.list():
            return
        job.status = status
        if not job.created_at:
            job.created_at = datetime.utcnow()
        if status == JobStatusEnum.JOB_STARTED_STATUS.value:
            job.started_at = datetime.utcnow()

        end_states = (JobStatusEnum.JOB_SUCCEEDED_STATUS.value,
                      JobStatusEnum.JOB_FAILED_STATUS.value)
        if status in end_states and licensed_job_ids:
            job.stopped_at = datetime.utcnow()
            _LOG.debug(f'Updating jobs statuses in LM')
            for licensed_job_id in licensed_job_ids:
                self.license_manager_service.update_job_in_license_manager(
                    job_id=licensed_job_id,
                    created_at=utc_iso(job.created_at),
                    started_at=utc_iso(job.started_at),
                    stopped_at=utc_iso(job.stopped_at),
                    status=status
                )
        self._save(job=job)
        return job
