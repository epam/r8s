from datetime import datetime

from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE, RESPONSE_SERVICE_UNAVAILABLE_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, GET_METHOD, DELETE_METHOD, ID_ATTR, \
    NAME_ATTR, USER_ID_ATTR, PARENT_ID_ATTR, SCAN_FROM_DATE_ATTR, \
    SCAN_TO_DATE_ATTR
from commons.constants import TENANTS_ATTR, CUSTOMER_ATTR, \
    SCAN_TIMESTAMP_ATTR, CLOUD_AWS
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.job import Job, JobStatusEnum
from services.abstract_api_handler_lambda import PARAM_USER_ID, \
    PARAM_USER_CUSTOMER
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-job-processor')

DEFAULT_SCAN_CLOUDS = [CLOUD_AWS]
DATE_FORMAT = '%Y_%m_%d'


class JobProcessor(AbstractCommandProcessor):
    def __init__(self, job_service: JobService,
                 application_service: RightSizerApplicationService,
                 environment_service: EnvironmentService,
                 customer_service: CustomerService,
                 tenant_service: TenantService,
                 settings_service: SettingsService,
                 shape_service: ShapeService,
                 shape_price_service: ShapePriceService,
                 parent_service: RightSizerParentService):
        self.job_service = job_service
        self.application_service = application_service
        self.environment_service = environment_service
        self.customer_service = customer_service
        self.tenant_service = tenant_service
        self.settings_service = settings_service
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service
        self.parent_service = parent_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            DELETE_METHOD: self.delete,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'job processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe job event: {event}')

        job_id = event.get(ID_ATTR)
        job_name = event.get(NAME_ATTR)
        applications = self.application_service.resolve_application(
            event=event
        )
        if not applications:
            _LOG.error(f'No suitable application found to describe jobs.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No suitable application found to describe jobs.'
            )
        if job_id:
            _LOG.debug(f'Describing job by id: \'{job_id}\'')
            jobs = [self.job_service.get_by_id(object_id=job_id)]
        elif job_name:
            _LOG.debug(f'Describing job by name \'{job_name}\'')
            jobs = [self.job_service.get_by_name(name=job_name)]
        else:
            _LOG.debug(f'Describing all jobs')
            jobs = self.job_service.list()

        if not jobs or jobs and all([job is None for job in jobs]):
            _LOG.debug(f'No jobs found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No jobs found matching given query'
            )

        _LOG.debug(f'Converting \'{len(jobs)}\' jobs to dto')
        job_dtos = [job.get_dto() for job in jobs]

        _LOG.debug(f'Response: {job_dtos}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=job_dtos
        )

    def post(self, event):
        _LOG.debug(f'Submit job event: {event}')
        validate_params(event, (USER_ID_ATTR, PARENT_ID_ATTR))

        parent_id = event.get(PARENT_ID_ATTR)
        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)

        if not parent:
            _LOG.error(f'Parent with id \'{parent_id}\' does not exist')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent with id \'{parent_id}\' does not exist'
            )

        applications = self.application_service.resolve_application(
            event=event
        )
        if not applications:
            _LOG.error(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )

        user_id = event.get(USER_ID_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)

        if user_customer != 'admin' and parent.customer_id \
                != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'customer \'{parent.customer_id}\' entities.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'User \'{user_id}\' is not authorize to affect '
                        f'customer \'{parent.customer_id}\' entities.'
            )

        envs = {
            "AWS_REGION": self.environment_service.aws_region(),
            "log_level": "DEBUG",
            "DEBUG": str(self.environment_service.is_debug())
        }
        meta_postponed_key = self.environment_service.meta_postponed_key()
        if meta_postponed_key:
            envs['META_POSTPONED_KEY'] = meta_postponed_key

        scan_customer = event.get(CUSTOMER_ATTR)
        if user_customer != 'admin' and scan_customer \
                and scan_customer != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'customer \'{parent.customer_id}\' entities.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'User \'{user_id}\' is not authorize to affect '
                        f'customer \'{parent.customer_id}\' entities.'
            )
        if not scan_customer and user_customer != 'admin':
            envs['SCAN_CUSTOMER'] = user_customer
        if scan_customer:
            customer_obj = self.customer_service.get(name=scan_customer)
            if not customer_obj:
                _LOG.error(f'Customer with name \'{scan_customer}\' does not '
                           f'exist')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Customer with name \'{scan_customer}\' does not '
                            f'exist'
                )
            envs['SCAN_CUSTOMER'] = scan_customer
        else:
            _LOG.debug(f'Setting SCAN_CUSTOMER as \'{parent.customer_id}\'')
            envs['SCAN_CUSTOMER'] = parent.customer_id

        scan_tenants = event.get(TENANTS_ATTR)
        if scan_tenants:
            _LOG.debug(f'Going to validate provided tenants to scan: '
                       f'{scan_tenants}')
            non_existing = []
            invalid_tenant_customer = []
            for tenant_name in scan_tenants:
                tenant_obj = self.tenant_service.get(tenant_name=tenant_name)
                if not tenant_obj:
                    non_existing.append(tenant_name)
                    continue
                if tenant_obj.customer_name not in \
                        (parent.customer_id, envs.get('SCAN_CUSTOMER')):
                    invalid_tenant_customer.append(tenant_name)
            if non_existing:
                _LOG.error(f'Some of the specified tenants does not exist: '
                           f'\'{non_existing}\'')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Some of the specified tenants does not exist: '
                            f'\'{non_existing}\''
                )
            if invalid_tenant_customer:
                _LOG.warning(f'Some of the specified tenants don\'t belong to '
                             f'parent customer '
                             f'{parent.customer_id} or specified for '
                             f'the current scan '
                             f'\'{envs.get("SCAN_CUSTOMER", "None")}\'.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Some of the specified tenants don\'t belong to '
                            f'parent customer '
                            f'{parent.customer_id} or specified for '
                            f'the current scan '
                            f'\'{envs.get("SCAN_CUSTOMER", "None")}\'.'
                )
            envs['SCAN_TENANTS'] = ','.join(scan_tenants)
        scan_from_date = event.get(SCAN_FROM_DATE_ATTR)
        if scan_from_date:
            _LOG.debug(f'Validating {SCAN_FROM_DATE_ATTR}')
            self._validate_scan_date(date_str=scan_from_date)
            envs[SCAN_FROM_DATE_ATTR.upper()] = scan_from_date

        scan_to_date = event.get(SCAN_TO_DATE_ATTR)
        if scan_to_date:
            _LOG.debug(f'Validating {SCAN_TO_DATE_ATTR}')
            self._validate_scan_date(date_str=scan_to_date)
            envs[SCAN_TO_DATE_ATTR.upper()] = scan_to_date

        scan_timestamp = event.get(SCAN_TIMESTAMP_ATTR)
        if scan_timestamp:
            _LOG.debug(f'Validating scan timestamp')
            if any([not ch.isdigit() for ch in str(scan_timestamp)]):
                _LOG.error(f'Invalid timestamp specified: timestamp must '
                           f'only contains digits.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Invalid timestamp specified: timestamp must '
                            f'only contains digits.'
                )
            envs['SCAN_TIMESTAMP'] = str(scan_timestamp)

        _LOG.debug(f'Going to submit job from application '
                   f'\'{parent.application_id}\' for cloud')
        response = self.job_service.submit_job(
            job_owner=user_id,
            parent_id=parent.parent_id,
            envs=envs
        )
        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def delete(self, event):
        _LOG.debug(f'Terminate job event: {event}')
        validate_params(event, (ID_ATTR,))

        user = event.get(PARAM_USER_ID)

        applications = self.application_service.resolve_application(
            event=event
        )
        if not applications:
            _LOG.error(f'No suitable applications found matching user.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No suitable applications found matching user.'
            )

        job_id = event.get(ID_ATTR)
        _LOG.debug(f'Describing job by id \'{job_id}\'')
        job: Job = self.job_service.get_by_id(object_id=job_id)

        user_customer = event.get(PARAM_USER_CUSTOMER)
        user_id = event.get(USER_ID_ATTR)

        application_ids = [app.application_id for app in applications]
        if user_customer != 'admin' and job.parent_id \
                not in application_ids:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'application jobs \'{job.parent_id}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'User \'{user_id}\' is not authorize to affect '
                        f'application jobs \'{job.parent_id}\''
            )

        if not job:
            _LOG.debug(f'Job with id \'{job_id}\' does not exist')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Job with id \'{job_id}\' does not exist'
            )

        if job.status in (JobStatusEnum.JOB_SUCCEEDED_STATUS,
                          JobStatusEnum.JOB_FAILED_STATUS):
            _LOG.error('Wrong job status, exiting')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Can not terminate job with status '
                        'SUCCEEDED or FAILED'
            )

        job.status = JobStatusEnum.JOB_FAILED_STATUS
        job.fail_reason = f'Terminated by user \'{user}\''

        _LOG.debug(f'Terminating Batch job')
        self.job_service.terminate_job(
            job_id=job_id,
            reason=job.fail_reason)
        _LOG.debug(f'Saving job')
        self.job_service.save(job=job)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'The job with id \'{job_id}\' will be terminated')

    def _validate_shape_presence(self, customer, scan_clouds):
        clouds_with_missing_shapes = []
        clouds_with_missing_prices = []
        for cloud in scan_clouds:
            shape_count = self.shape_service.count(cloud=cloud)
            shape_price_count = self.shape_price_service.count(
                customer=customer,
                cloud=cloud
            )
            if not shape_count:
                clouds_with_missing_shapes.append(cloud)
            if not shape_price_count:
                clouds_with_missing_prices.append(cloud)
        errors = []
        if clouds_with_missing_shapes:
            message = f'Improperly configured. Missing shape data for ' \
                      f'clouds: {", ".join(clouds_with_missing_shapes)}'
            errors.append(message)
        if clouds_with_missing_prices:
            message = f'Improperly configured. Missing shape pricing data ' \
                      f'for clouds: {", ".join(clouds_with_missing_shapes)}'
            errors.append(message)

        if errors:
            _LOG.error(f'Improperly configured: {errors}')
            return build_response(
                code=RESPONSE_SERVICE_UNAVAILABLE_CODE,
                content=', '.join(errors)
            )

    @staticmethod
    def _validate_scan_date(date_str):
        try:
            datetime.strptime(date_str, DATE_FORMAT)
        except (ValueError, TypeError):
            _LOG.error(f'Invalid date specified: \'{date_str}\'. Date must '
                       f'be in {DATE_FORMAT} format.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid date specified: \'{date_str}\'. Date must '
                        f'be in {DATE_FORMAT} format.'
            )
