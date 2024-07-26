from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, ID_ATTR, REPORT_TYPE_ATTR, \
    CUSTOMER_ATTR, TENANT_ATTR, REGION_ATTR, CLOUD_ATTR, INSTANCE_ID_ATTR, \
    DETAILED_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.job import Job, JobStatusEnum
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER

from services.job_service import JobService
from services.report_service import ReportService

from modular_sdk.services.tenant_service import TenantService
from modular_sdk.models.tenant import Tenant

_LOG = get_logger('r8s-report-processor')


class ReportProcessor(AbstractCommandProcessor):
    def __init__(self, job_service: JobService,
                 report_service: ReportService,
                 tenant_service: TenantService):
        self.job_service = job_service
        self.report_service = report_service
        self.tenant_service = tenant_service
        self.report_type_mapping = {
            None: self.general_report,
            'download': self.download_report
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        if not method == GET_METHOD:
            message = f'Unable to handle command {method} in ' \
                      f'report processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        report_type = event.get(REPORT_TYPE_ATTR)
        handler = self.report_type_mapping.get(report_type)

        if not handler:
            message = f'No handler for report type \'{report_type}\' ' \
                      f'available'
            _LOG.error(message)
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return handler(event=event)

    def general_report(self, event):
        _LOG.debug(f'Describe general job report event: {event}')

        validate_params(event, (ID_ATTR,))
        job_id = event.get(ID_ATTR)
        detailed = event.get(DETAILED_ATTR)
        if detailed:
            detailed = any([item in detailed.lower()
                            for item in ('true', 't')])

        customer = event.get(CUSTOMER_ATTR)
        cloud = event.get(CLOUD_ATTR)
        tenant = event.get(TENANT_ATTR)
        region = event.get(REGION_ATTR)
        instance_id = event.get(INSTANCE_ID_ATTR)

        _LOG.debug(f'Describing job by id: \'{job_id}\'')
        job: Job = self.job_service.get_by_id(object_id=job_id)

        if not job:
            _LOG.debug(f'Job with id \'{job_id}\' does not exist')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Job with id \'{job_id}\' does not exist'
            )
        if job.status != JobStatusEnum.JOB_SUCCEEDED_STATUS:
            _LOG.debug(f'Job \'{job_id}\' must be succeeded.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Job \'{job_id}\' must have SUCCEEDED status.'
            )

        if not customer:
            _LOG.debug(f'Event customer not specified, resolving')
            customer = self.resolve_customer(
                user_customer=event.get(PARAM_USER_CUSTOMER),
                job=job
            )
            _LOG.debug(f'Resolved customer: {customer}')

        _LOG.debug(f'Going to generate report for job \'{job_id}\'')
        reports = self.report_service.get_job_report(
            job=job, detailed=detailed, customer=customer, cloud=cloud,
            tenant=tenant, region=region, instance_id=instance_id)
        _LOG.debug(f'Report: {reports}')
        if not reports:
            _LOG.error(f'No results found matching given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No results found matching given query'
            )
        return build_response(
            code=RESPONSE_OK_CODE,
            content=reports
        )

    def download_report(self, event):
        _LOG.debug(f'Report for downloading event: {event}')

        validate_params(event, (ID_ATTR,))

        customer = event.get(CUSTOMER_ATTR)
        tenant = event.get(TENANT_ATTR)
        region = event.get(REGION_ATTR)

        job_id = event.get(ID_ATTR)

        _LOG.debug(f'Describing job by id: \'{job_id}\'')
        job: Job = self.job_service.get_by_id(object_id=job_id)

        if not job:
            _LOG.debug(f'Job with id \'{job_id}\' does not exist')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Job with id \'{job_id}\' does not exist'
            )
        if job.status != JobStatusEnum.JOB_SUCCEEDED_STATUS:
            _LOG.debug(f'Job \'{job_id}\' must be succeeded.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Job \'{job_id}\' must have SUCCEEDED status.'
            )
        if not customer:
            _LOG.debug(f'Event customer not specified, resolving')
            customer = self.resolve_customer(
                user_customer=event.get(PARAM_USER_CUSTOMER),
                job=job
            )
            _LOG.debug(f'Resolved customer: {customer}')
        _LOG.debug(f'Going to generate report for job \'{job_id}\'')
        report = self.report_service.get_download_report(
            job=job, customer=customer, tenant=tenant, region=region)
        _LOG.debug(f'Response: {report}')
        if not report:
            _LOG.debug(f'No results found matching given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No results found matching given query'
            )
        return build_response(
            code=RESPONSE_OK_CODE,
            content=report
        )

    def resolve_customer(self, user_customer, job: Job):
        if user_customer and user_customer != 'admin':
            return user_customer
        if not job.tenant_status_map:
            return
        tenant_name = next(iter(job.tenant_status_map))
        tenant = self.tenant_service.get(
            tenant_name=tenant_name,
            attributes_to_get=[Tenant.name, Tenant.customer_name]
        )
        if tenant:
            return tenant.customer_name
