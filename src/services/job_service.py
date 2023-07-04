from mongoengine import DoesNotExist, ValidationError

from commons import get_iso_timestamp, build_response, \
    RESPONSE_INTERNAL_SERVER_ERROR
from commons.constants import PARAM_NATIVE_JOB_ID
from commons.log_helper import get_logger
from models.job import Job
from services.clients.batch import BatchClient
from services.environment_service import EnvironmentService

_LOG = get_logger('r8s-job-service')


class JobService:
    def __init__(self, environment_service: EnvironmentService,
                 batch_client: BatchClient):
        self.environment_service = environment_service
        self.batch_client = batch_client

    def submit_job(self, job_owner: str, parent_id: str, envs):
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
            parent_id=parent_id)
        _LOG.debug(f'Saving job')
        self.save(job=job)
        return job.get_dto()

    def terminate_job(self, job_id, reason):
        return self.batch_client.terminate_job(job_id=job_id, reason=reason)

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
    def save(job: Job):
        job.save()

    @staticmethod
    def _delete(job: Job):
        job.delete()
