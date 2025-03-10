from datetime import datetime
from typing import List
import os
from modular_sdk.commons.constants import (RIGHTSIZER_LICENSES_PARENT_TYPE,
                                           ParentScope, ApplicationType,
                                           ParentType)
from modular_sdk.models.application import Application
from modular_sdk.models.tenant import Tenant
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE, RESPONSE_SERVICE_UNAVAILABLE_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import CLOUD_AWS, TENANTS_ATTR, \
    ENV_TENANT_CUSTOMER_INDEX, FORBIDDEN_ATTR, ALLOWED_ATTR, \
    REMAINING_BALANCE_ATTR, ENV_LM_TOKEN_LIFETIME_MINUTES, LIMIT_ATTR, \
    APPLICATION_ID_ATTR, MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE, \
    APPLICATION_TENANTS_ALL, MAESTRO_RIGHTSIZER_APPLICATION_TYPE
from commons.constants import POST_METHOD, GET_METHOD, DELETE_METHOD, ID_ATTR, \
    NAME_ATTR, USER_ID_ATTR, PARENT_ID_ATTR, SCAN_FROM_DATE_ATTR, \
    SCAN_TO_DATE_ATTR, TENANT_LICENSE_KEY_ATTR, PARENT_SCOPE_SPECIFIC_TENANT
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.job import Job, JobStatusEnum
from services.abstract_api_handler_lambda import PARAM_USER_ID, \
    PARAM_USER_CUSTOMER
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-job-processor')

DEFAULT_SCAN_CLOUDS = [CLOUD_AWS]
DATE_FORMAT = '%Y-%m-%d'


class JobProcessor(AbstractCommandProcessor):
    def __init__(self, job_service: JobService,
                 application_service: RightSizerApplicationService,
                 environment_service: EnvironmentService,
                 customer_service: CustomerService,
                 tenant_service: TenantService,
                 settings_service: SettingsService,
                 shape_service: ShapeService,
                 shape_price_service: ShapePriceService,
                 parent_service: RightSizerParentService,
                 license_service: LicenseService,
                 license_manager_service: LicenseManagerService):
        self.job_service = job_service
        self.application_service = application_service
        self.environment_service = environment_service
        self.customer_service = customer_service
        self.tenant_service = tenant_service
        self.settings_service = settings_service
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service
        self.parent_service = parent_service
        self.license_service = license_service
        self.license_manager_service = license_manager_service

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
        limit = event.get(LIMIT_ATTR)
        if not applications:
            _LOG.error(f'No suitable application found to describe jobs.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No suitable application found to describe jobs.'
            )

        if limit:
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                _LOG.error(f'{LIMIT_ATTR} attribute must be a valid int')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'{LIMIT_ATTR} attribute must be a valid int'
                )

        if job_id:
            _LOG.debug(f'Describing job by id: \'{job_id}\'')
            jobs = [self.job_service.get_by_id(object_id=job_id)]
        elif job_name:
            _LOG.debug(f'Describing job by name \'{job_name}\'')
            jobs = [self.job_service.get_by_name(name=job_name)]
        else:
            _LOG.debug(f'Describing all jobs')
            jobs = self.job_service.list(limit=limit)

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
        validate_params(event, (USER_ID_ATTR,))

        resolved_applications = self.application_service.resolve_application(
            event=event
        )
        if not resolved_applications:
            _LOG.error('Application matching given query '
                       'does not exist')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Application matching given query '
                        'does not exist'
            )
        if len(resolved_applications) > 1:
            _LOG.error('More than one matching application found. Please '
                       'try to specify application_id explicitly')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='More than one matching application found. Please '
                        'try to specify application_id explicitly'
            )
        licensed_application = resolved_applications[0]

        if (licensed_application.type !=
                MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE):
            _LOG.error(f'Application of '
                       f'{MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE} '
                       f'type required.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Application of '
                        f'{MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE} '
                        f'type required.'
            )

        parent_id = event.get(PARENT_ID_ATTR)
        _LOG.debug(f'Extracting application {licensed_application.application_id} parents. '
                   f'Parent id {parent_id}')
        parents = self._get_parents(
            application_id=licensed_application.application_id,
            parent_id=parent_id
        )

        user_id = event.get(USER_ID_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)

        if user_customer != 'admin' and licensed_application.customer_id \
                != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'customer \'{licensed_application.customer_id}\' '
                         f'entities.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'User \'{user_id}\' is not authorize to affect '
                        f'customer \'{licensed_application.customer_id}\' '
                        f'entities.'
            )

        applications = self.application_service.list(
            customer=licensed_application.customer_id,
            deleted=False,
            _type=ApplicationType.RIGHTSIZER,
            limit=1
        )
        application = next(applications, None)
        if not application:
            _LOG.debug('No RIGHTSIZER application '
                       'found matching given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No RIGHTSIZER application '
                        'found matching given query'
            )

        envs = {
            "AWS_REGION": self.environment_service.aws_region(),
            "log_level": os.environ.get('log_level', 'ERROR'),
            "licensed_application_id": licensed_application.application_id,
            "application_id": application.application_id,
            "FORCE_RESCAN": os.environ.get('force_rescan', "False"),
            "DEBUG": str(self.environment_service.is_debug()),
            ENV_LM_TOKEN_LIFETIME_MINUTES: str(
                self.environment_service.lm_token_lifetime_minutes())
        }
        if parent_id:
            envs['parent_id'] = parents[0].parent_id
        meta_postponed_key = self.environment_service.meta_postponed_key()
        if meta_postponed_key:
            envs['META_POSTPONED_KEY'] = meta_postponed_key

        rate_limit = self.environment_service.tenants_customer_name_index_rcu()
        _LOG.debug(f'Rate limiting on Tenants customer index rcu: '
                   f'{rate_limit}')
        envs[ENV_TENANT_CUSTOMER_INDEX] = str(rate_limit)

        scan_tenants = event.get(TENANTS_ATTR, [])
        if scan_tenants:
            _LOG.debug(f'Validating user-provided scan tenants: '
                       f'{scan_tenants}')
            self._validate_input_tenants(
                application=licensed_application,
                parents=parents,
                input_scan_tenants=scan_tenants
            )
        else:
            _LOG.debug(f'Resolving tenant names from parents: '
                       f'{", ".join([p.parent_id for p in parents])}')
            scan_tenants = self.parent_service.resolve_tenant_names(
                parents=parents,
                cloud=licensed_application.meta.cloud
            )
        _LOG.debug(f'Setting scan_tenants env to '
                   f'\'{scan_tenants}\'')
        envs['SCAN_TENANTS'] = ','.join(scan_tenants)

        application_meta = self.application_service.get_application_meta(
            application=licensed_application)
        _LOG.debug(f'Checking permission to submit job on license '
                   f'\'{application_meta.license_key}\' '
                   f'for tenants: {scan_tenants}')
        tenant_status_map = self._validate_licensed_job(
            application=licensed_application,
            license_key=application_meta.license_key,
            scan_tenants=scan_tenants
        )

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

        _LOG.debug(f'Going to submit job from application '
                   f'\'{licensed_application.application_id}\'')
        response = self.job_service.submit_job(
            job_owner=user_id,
            application_id=licensed_application.application_id,
            parent_id=parent_id,
            envs=envs,
            tenant_status_map=tenant_status_map
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

    def _get_parents(self, application_id: str, parent_id: str = None):
        if parent_id:
            _LOG.debug(f'Extracting parent {parent_id}')
            parent = self.parent_service.get_parent_by_id(
                parent_id=parent_id)
            error_message = None
            if not parent:
                error_message = f'Parent {parent_id} does not exist'
            elif not parent.type == RIGHTSIZER_LICENSES_PARENT_TYPE:
                error_message = (f'Parent {parent_id} must have '
                                 f'{RIGHTSIZER_LICENSES_PARENT_TYPE} type')

            elif not parent.application_id == application_id:
                error_message = (f'Parent {parent_id} is not linked '
                                 f'to application {application_id}')
            if error_message:
                _LOG.error(error_message)
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=error_message
                )
            parents = [parent]
        else:
            application = self.application_service.get_application_by_id(
                application_id=application_id)
            _LOG.debug(f'Searching for application {application_id} parents')
            parents = self.parent_service.list_application_parents(
                application_id=application.application_id,
                only_active=True
            )
        parents = [parent for parent in parents
                   if parent.scope != ParentScope.DISABLED]
        if not parents:
            _LOG.error(f'No matching parents found.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No matching parents found.'
            )
        return parents

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

    def _validate_licensed_job(self, application: Application,
                               license_key: str,
                               scan_tenants: List[str]):
        _LOG.debug(f'Resolving Tenant list')
        if not scan_tenants:
            _LOG.error(f'At least 1 tenant must be specified '
                       f'for licensed jobs.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'At least 1 tenant must be specified '
                        f'for licensed jobs.'
            )
        _license = self.license_service.get_license(license_key)
        if self.license_service.is_expired(_license):
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Affected license has expired'
            )
        tenant_license_key = _license.customers.get(
            application.customer_id, {}).get(TENANT_LICENSE_KEY_ATTR)
        _LOG.debug(f'Validating permission to submit licensed job.')
        return self._ensure_job_is_allowed(
            customer=application.customer_id,
            tenant_names=scan_tenants,
            tlk=tenant_license_key
        )

    def _ensure_job_is_allowed(self, customer, tenant_names: list, tlk: str,
                               allow_partial=True):
        _LOG.info(f'Going to check for permission to exhaust'
                  f'{tlk} TenantLicense(s).')
        allowance_map = self.license_manager_service.get_allowance_map(
            customer=customer, tenants=tenant_names,
            tenant_license_keys=[tlk])
        if not allowance_map:
            message = f'Tenants:\'{", ".join(tenant_names)}\' ' \
                      f'could not be granted ' \
                      f'to start a licensed job.'
            return build_response(
                content=message, code=RESPONSE_FORBIDDEN_CODE
            )
        tlk_allowance_map = allowance_map.get(tlk, {})

        forbidden = tlk_allowance_map.get(FORBIDDEN_ATTR)
        allowed = tlk_allowance_map.get(ALLOWED_ATTR)
        remaining_balance = tlk_allowance_map.get(REMAINING_BALANCE_ATTR)
        if not allow_partial:
            if forbidden:
                _LOG.error(f'Licensed job is forbidden for tenants: '
                           f'{", ".join(forbidden)}')
                return build_response(
                    code=RESPONSE_FORBIDDEN_CODE,
                    content=f'Licensed job is forbidden for tenants: '
                            f'{", ".join(forbidden)}'
                )
            if remaining_balance and len(allowed) > remaining_balance:
                error = f'Remaining job balance \'{remaining_balance}\' ' \
                        f'is greater than requested number of tenants: ' \
                        f'{", ".join(allowed)}'
                _LOG.error(error)
                return build_response(
                    code=RESPONSE_FORBIDDEN_CODE,
                    content=error
                )

        _LOG.info(f'Permission to submit job has been granted for tenants: '
                  f'{tenant_names}.')
        return self.job_service.build_job_tenant_map(forbidden=forbidden,
                                                     allowed=allowed,
                                                     limit=remaining_balance)

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

    def _validate_input_tenants(self, application: Application,
                                parents: List[Parent],
                                input_scan_tenants: list = None) -> list:
        allowed_tenants = []
        for parent in parents:
            if parent.scope == ParentScope.ALL:
                allowed_tenants.append(APPLICATION_TENANTS_ALL)
            elif parent.scope == ParentScope.SPECIFIC:
                allowed_tenants.append(parent.tenant_name)

        app_meta = self.application_service.get_application_meta(
            application=application)
        if not isinstance(input_scan_tenants, list):
            _LOG.error(f'{TENANTS_ATTR} attribute must be a list.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'{TENANTS_ATTR} attribute must be a list.'
            )
        invalid_tenants = []
        for tenant_name in input_scan_tenants:
            _LOG.debug(f'Validating tenant \'{tenant_name}\'')
            tenant_obj: Tenant = self.tenant_service.get(
                tenant_name=tenant_name)
            if not tenant_obj:
                invalid_tenants.append(tenant_name)
                continue
            if tenant_obj.customer_name != application.customer_id:
                _LOG.warning(f'Tenant customer '
                             f'\'{tenant_obj.customer_name}\' '
                             f'does not match with parent '
                             f'customer \'{application.customer_id}\'')
                invalid_tenants.append(tenant_name)
                continue
            if tenant_obj.cloud != app_meta.cloud:
                _LOG.warning(f'Tenant cloud \'{tenant_obj.cloud}\' '
                             f'does not match with parent '
                             f'cloud {app_meta.cloud}.')
                invalid_tenants.append(tenant_name)
                continue
            if APPLICATION_TENANTS_ALL in allowed_tenants:
                continue
            if tenant_name not in allowed_tenants:
                _LOG.warning(f'Scanning tenant \'{tenant_name}\' '
                             f'is forbidden for application '
                             f'\'{application.application_id}\'')
                invalid_tenants.append(tenant_name)

        if invalid_tenants:
            message = f'Some of the specified tenants are invalid for ' \
                      f'application \'{application.application_id}\': ' \
                      f'{", ".join(invalid_tenants)}'
            _LOG.error(message)
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=message
            )
