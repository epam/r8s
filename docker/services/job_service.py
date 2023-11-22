from datetime import datetime

from mongoengine import DoesNotExist, ValidationError

from commons.log_helper import get_logger
from commons.profiler import profiler
from commons.time_helper import utc_iso
from models.job import Job, JobStatusEnum, JobTenantStatusEnum
from services.environment_service import EnvironmentService
from services.license_manager_service import LicenseManagerService

_LOG = get_logger('r8s-job-service')


class JobService:
    def __init__(self, environment_service: EnvironmentService,
                 license_manager_service: LicenseManagerService):
        self.environment_service = environment_service
        self.license_manager_service = license_manager_service

    @staticmethod
    def list(limit: int = None):
        return list(Job.objects.all().limit(limit))

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

    def set_status(self, job: Job, status: str):
        if status not in JobStatusEnum.list():
            return
        job.status = status
        if not job.created_at:
            job.created_at = datetime.utcnow()
        if not job.started_at:
            job.started_at = datetime.utcnow()
        if status == JobStatusEnum.JOB_STARTED_STATUS.value:
            job.started_at = datetime.utcnow()
        if status in (JobStatusEnum.JOB_FAILED_STATUS.value,
                      JobStatusEnum.JOB_SUCCEEDED_STATUS.value):
            job.stopped_at = datetime.utcnow()
        self._save(job=job)
        return job

    @staticmethod
    def get_scan_tenants(job: Job):
        scan_tenants = []
        for tenant, status in job.tenant_status_map.items():
            if status != JobTenantStatusEnum.TENANT_FORBIDDEN_STATUS.value:
                scan_tenants.append(tenant)
        return scan_tenants

    @profiler(execution_step=f'lm_update_job_status')
    def set_licensed_job_status(self, job: Job, tenant: str,
                                status: JobTenantStatusEnum,
                                customer: str = None):
        allowed_statuses = (JobTenantStatusEnum.TENANT_FAILED_STATUS,
                            JobTenantStatusEnum.TENANT_SUCCEEDED_STATUS)
        if tenant not in job.tenant_status_map or \
                status not in allowed_statuses:
            return
        job.tenant_status_map[tenant] = status.value
        self._save(job=job)

        licensed_job_id = f'{job.id}:{tenant}'
        self.license_manager_service.update_job_in_license_manager(
            job_id=licensed_job_id,
            created_at=utc_iso(job.created_at),
            started_at=utc_iso(job.started_at),
            stopped_at=utc_iso(),
            status=status.value,
            customer=customer
        )
