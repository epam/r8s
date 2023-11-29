from typing import List, Optional

from mongoengine import DoesNotExist, ValidationError

from commons import get_iso_timestamp, build_response, \
    RESPONSE_INTERNAL_SERVER_ERROR
from commons.constants import PARAM_NATIVE_JOB_ID
from commons.log_helper import get_logger
from models.job import Job, JobTenantStatusEnum
from services.clients.batch import BatchClient
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-job-service')


class JobService:
    def __init__(self, environment_service: EnvironmentService,
                 batch_client: BatchClient):
        self.environment_service = environment_service
        self.batch_client = batch_client

    def submit_job(self, job_owner: str,
                   application_id: str, envs,
                   tenant_status_map: dict,
                   parent_id: str = None):
        submitted_at = get_iso_timestamp()
        job_name = f'{job_owner}-{submitted_at}'
        job_name = ''.join([ch if ch.isalnum() or ch in ('-', '_')
                            else '_' for ch in job_name])
        _LOG.debug(f'Submitting job with name: \'{job_name}\'')
        response = self.batch_client.submit_job(
            job_name=job_name,
            job_queue=self.environment_service.get_batch_job_queue(),
            job_definition=self.environment_service.get_batch_job_def(),
            environment_variables=envs,
            command=f'python /home/r8s/executor.py'
        )
        _LOG.debug(f'Batch response: {response}')
        if not response:
            return build_response(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content='AWS Batch failed to respond')
        _LOG.debug(f'Creating Job')
        job = Job(
            id=response[PARAM_NATIVE_JOB_ID],
            name=job_name,
            owner=job_owner,
            submitted_at=submitted_at,
            job_queue=self.environment_service.get_batch_job_queue(),
            application_id=application_id,
            parent_id=parent_id,
            tenant_status_map=tenant_status_map)
        _LOG.debug(f'Saving job')
        self.save(job=job)
        return job.get_dto()

    def terminate_job(self, job_id, reason):
        return self.batch_client.terminate_job(job_id=job_id, reason=reason)

    @staticmethod
    def build_job_tenant_map(forbidden: List[str], allowed: List[str],
                             limit: int = None):
        tenant_status_map = {}

        for forbidden_tenant in forbidden:
            tenant_status_map[forbidden_tenant] = \
                JobTenantStatusEnum.TENANT_FORBIDDEN_STATUS.value

        for allowed_tenant in allowed:
            tenant_status_map[allowed_tenant] = \
                JobTenantStatusEnum.TENANT_RUNNABLE_STATUS.value

        if limit and len(allowed) > limit:
            _LOG.warning(f'Tenants \'{", ".join(allowed[-limit:])}\' status '
                         f'will be forbidden due to exceeded '
                         f'remaining job balance')
            for tenant in allowed[-limit:]:
                tenant_status_map[tenant] = \
                    JobTenantStatusEnum.TENANT_FORBIDDEN_STATUS.value

        _LOG.debug(f'Tenant status map: {tenant_status_map}')
        return tenant_status_map

    @staticmethod
    def list(limit: int = None):
        return list(Job.objects.all().order_by('-submitted_at').limit(limit))

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
    def save(job: Job):
        job.save()

    @staticmethod
    def _delete(job: Job):
        job.delete()
