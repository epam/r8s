from datetime import datetime

from commons import raise_error_response, RESPONSE_INTERNAL_SERVER_ERROR, \
    build_response
from commons.log_helper import get_logger
from services import SERVICE_PROVIDER
from services.abstract_lambda import AbstractLambda, PARAM_NATIVE_JOB_ID
from services.job_service import JobService
from services.ssm_service import SSMService

PARAM_STOPPED_AT = 'stoppedAt'
PARAM_STARTED_AT = 'startedAt'
PARAM_CREATED_AT = 'createdAt'
PARAM_DETAIL = 'detail'

PARAM_FAILED = 'FAILED'
PARAM_SUCCEEDED = 'SUCCEEDED'

_LOG = get_logger('custodian-job-updater')


class JobUpdater(AbstractLambda):

    def __init__(self, job_service: JobService, ssm_service: SSMService):
        self.job_service = job_service
        self.ssm_service = ssm_service

    def validate_request(self, event) -> dict:
        errors = {}
        if event.get('source') != 'aws.batch':
            errors['source'] = 'Only \'aws.batch\' events supported'
        detail = event.get('detail')
        if not detail:
            errors['detail'] = 'Attribute \'detail\' is required'
        else:
            if not detail.get(PARAM_NATIVE_JOB_ID):
                errors[f'detail.{PARAM_NATIVE_JOB_ID}'] = \
                    f'Attribute \'detail.{PARAM_NATIVE_JOB_ID}\' is required'
        return errors

    def handle_request(self, event, context):
        detail = event[PARAM_DETAIL]
        job_id = detail[PARAM_NATIVE_JOB_ID]
        job_item = self.job_service.get_by_id(job_id)
        if not job_item:
            raise_error_response(
                RESPONSE_INTERNAL_SERVER_ERROR,
                f'Missed Job document with jobId {job_id} in Database')
        if not job_item.created_at and detail.get(PARAM_CREATED_AT):
            job_item.created_at = self.timestamp_to_iso(
                detail[PARAM_CREATED_AT])
        if not job_item.started_at and detail.get(PARAM_STARTED_AT):
            job_item.started_at = self.timestamp_to_iso(
                detail[PARAM_STARTED_AT])
        if not job_item.stopped_at and detail.get(PARAM_STOPPED_AT):
            job_item.stopped_at = self.timestamp_to_iso(
                detail[PARAM_STOPPED_AT])
        if not job_item.job_queue:
            job_item.job_queue = detail['jobQueue']

        job_item.status = detail['status']

        self.job_service.save(job=job_item)
        return build_response(content={'job_id': job_id})

    @staticmethod
    def timestamp_to_iso(timestamp):
        date = datetime.fromtimestamp(timestamp / 1000)
        return date.isoformat()


HANDLER = JobUpdater(
    job_service=SERVICE_PROVIDER.job_service(),
    ssm_service=SERVICE_PROVIDER.ssm_service()
)


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
