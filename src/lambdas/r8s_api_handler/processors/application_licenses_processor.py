from modular_sdk.commons.constants import AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, \
    RIGHTSIZER_LICENSES_TYPE
from modular_sdk.commons import ModularException
from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    CLOUD_ATTR, CLOUD_ALL, TENANT_LICENSE_KEY_ATTR, \
    LICENSE_KEY_ATTR, CUSTOMER_ATTR, APPLICATION_TENANTS_ALL, FORCE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.algorithm import Algorithm
from models.application_attributes import RightsizerLicensesApplicationMeta
from models.license import License
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.algorithm_service import AlgorithmService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-application-licenses-processor')

CLOUDS = [AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, CLOUD_ALL]


class ApplicationLicensesProcessor(AbstractCommandProcessor):
    def __init__(self, algorithm_service: AlgorithmService,
                 customer_service: CustomerService,
                 application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 license_service: LicenseService,
                 license_manager_service: LicenseManagerService):
        self.algorithm_service = algorithm_service
        self.customer_service = customer_service
        self.application_service = application_service
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
                      f'job definition processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe application licenses event: {event}')

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=RIGHTSIZER_LICENSES_TYPE)

        if not applications:
            _LOG.warning('No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No application found matching given query.'
            )

        response = [self.application_service.get_dto(application)
                    for application in applications]
        _LOG.debug(f'Response: {response}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event):
        _LOG.debug(f'Create licensed application event: {event}')
        validate_params(event, (CUSTOMER_ATTR, DESCRIPTION_ATTR,
                                CLOUD_ATTR, TENANT_LICENSE_KEY_ATTR))

        customer = event.get(CUSTOMER_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)

        _LOG.debug(f'Validating user access to customer \'{customer}\'')
        if not self._is_allowed_customer(user_customer=user_customer,
                                         customer=customer):
            _LOG.warning(f'User is not allowed to create application for '
                         f'customer \'{customer}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You are not allowed to create application for '
                        f'customer \'{customer}\''
            )

        _LOG.debug(f'Validating customer existence \'{customer}\'')
        customer_obj = self.customer_service.get(name=customer)
        if not customer_obj:
            _LOG.warning(f'Customer \'{customer}\' does not exist')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Customer \'{customer}\' does not exist'
            )

        cloud = event.get(CLOUD_ATTR).upper()
        _LOG.debug(f'Validation cloud: {cloud}')
        if not isinstance(cloud, str) or cloud not in CLOUDS:
            _LOG.error(f'Invalid cloud specified \'{cloud}\'. '
                       f'Available clouds: {", ".join(CLOUDS)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid cloud specified \'{cloud}\'. '
                        f'Available clouds: {", ".join(CLOUDS)}'
            )

        tenant_license_key = event.get(TENANT_LICENSE_KEY_ATTR)
        _LOG.debug(f'Activating license \'{tenant_license_key}\' '
                   f'for customer')
        license_obj = self.activate_license(
            tenant_license_key=tenant_license_key,
            customer=customer
        )
        self._execute_license_sync(
            license_obj=license_obj,
            customer=customer
        )
        license_key = license_obj.license_key
        algorithm_map = license_obj.algorithm_mapping

        for resource_type, algorithm_name in algorithm_map.items():
            self._validate_algorithm(
                algorithm_name=algorithm_name,
                customer=customer,
                cloud=cloud
            )

        description = event.get(DESCRIPTION_ATTR)
        if not description:
            _LOG.error('Description can\'t be empty.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Description can\'t be empty.'
            )

        tenants = self.license_service.list_allowed_tenants(
            license_obj=license_obj,
            customer=customer_obj.name
        )
        if not tenants:
            tenants = [APPLICATION_TENANTS_ALL]

        meta = RightsizerLicensesApplicationMeta(
            cloud=cloud,
            algorithm_map=algorithm_map,
            license_key=license_key,
            tenants=tenants
        )
        _LOG.debug(f'Application meta {meta.as_dict()}')

        _LOG.debug('Creating application')
        application = self.application_service.build(
            customer_id=customer_obj.name,
            type=RIGHTSIZER_LICENSES_TYPE,
            description=description,
            is_deleted=False,
            meta=meta.as_dict(),
            created_by=event.get(PARAM_USER_SUB)
        )
        _LOG.debug('Saving application')
        self.application_service.save(application=application)

        _LOG.debug('Preparing response')
        response = self.application_service.get_dto(application=application)

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def delete(self, event):
        _LOG.debug(f'Delete licenses application event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR,))

        application_id = event.get(APPLICATION_ID_ATTR)
        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=RIGHTSIZER_LICENSES_TYPE)

        target_application = None
        for application in applications:
            if application.application_id == application_id:
                target_application = application

        if not target_application:
            _LOG.warning(f'Application {application_id} not found.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Application {application_id} not found.'
            )
        force = event.get(FORCE_ATTR)
        try:
            if force:
                self.application_service.force_delete(
                    application=target_application)
            else:
                self.application_service.mark_deleted(
                    application=target_application)
        except ModularException as e:
            return build_response(
                code=e.code,
                content=e.content
            )

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Application \'{application_id}\' has been deleted.'
        )

    def activate_license(self, tenant_license_key: str, customer: str):
        _response = self.license_manager_service.activate_customer(
            customer, tenant_license_key
        )
        if not _response:
            _message = f'License manager does not allow to activate ' \
                       f'tenant license \'{tenant_license_key}\'' \
                       f' for customer \'{customer}\''
            _LOG.warning(_message)
            return build_response(code=RESPONSE_FORBIDDEN_CODE,
                                  content=_message)
        license_key = _response.get(LICENSE_KEY_ATTR)
        license_obj = self.license_service.get_license(license_key)
        if not license_obj:
            _LOG.info(f'License object with id \'{license_key}\' does '
                      f'not exist yet. Creating.')
            license_obj = self.license_service.create({
                LICENSE_KEY_ATTR: license_key})
        if not license_obj.customers or not license_obj.customers.get(
                customer):
            license_obj.customers = {customer: {}}

        license_obj.customers.get(customer)[
            TENANT_LICENSE_KEY_ATTR] = tenant_license_key
        _LOG.info('Going to save license object')
        license_obj.save()

        return license_obj

    def _execute_license_sync(self, license_obj: License, customer: str):
        _LOG.info(f'Syncing license \'{license_obj.license_key}\'')
        response = self.license_manager_service.synchronize_license(
            license_key=license_obj.license_key,
            customer=customer
        )
        if response.status_code != 200:
            return

        license_data = response.json()['items'][0]

        _LOG.debug(f'Updating license {license_obj.license_key}')
        license_obj = self.license_service.update_license(
            license_obj=license_obj,
            license_data=license_data
        )
        _LOG.debug('Updating licensed algorithms')
        self.algorithm_service.sync_licensed_algorithm(
            license_data=license_data,
            customer=customer
        )
        return license_obj

    @staticmethod
    def _is_allowed_customer(user_customer, customer):
        if user_customer == 'admin':
            return True
        if user_customer == customer:
            return True
        return False

    def _validate_algorithm(self, algorithm_name: str, customer: str,
                            cloud: str):
        _LOG.debug(f'Validating algorithm \'{algorithm_name}\'')
        algorithm_obj: Algorithm = self.algorithm_service.get_by_name(
            name=algorithm_name)
        if not algorithm_obj or algorithm_obj.customer != customer:
            _LOG.error(f'Algorithm \'{algorithm_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm_name}\' does not exist.'
            )
        if cloud != CLOUD_ALL and cloud != algorithm_obj.cloud.value:
            _LOG.error(f'Algorithm \'{algorithm_name}\' is not suitable for '
                       f'cloud \'{cloud}\'. Algorithm\'s cloud: '
                       f'{algorithm_obj.cloud.value}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm_name}\' is not suitable for '
                        f'cloud \'{cloud}\'. Algorithm\'s cloud: '
                        f'{algorithm_obj.cloud.value}'
            )
