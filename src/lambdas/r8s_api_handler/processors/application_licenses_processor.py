from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, \
    RIGHTSIZER_LICENSES_TYPE
from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, build_response, \
    RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    CLOUD_ATTR, CLOUD_ALL, TENANT_LICENSE_KEY_ATTR, \
    LICENSE_KEY_ATTR, CUSTOMER_ATTR, FORCE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.application_attributes import RightsizerLicensesApplicationMeta
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.algorithm_service import AlgorithmService
from services.license_manager_service import LicenseManagerService
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
                 license_manager_service: LicenseManagerService):
        self.algorithm_service = algorithm_service
        self.customer_service = customer_service
        self.application_service = application_service
        self.parent_service = parent_service
        self.license_manager_service = license_manager_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            DELETE_METHOD: self.delete,
        }

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
        license_key = self.activate_license(
            tenant_license_key=tenant_license_key,
            customer=customer
        )

        application = self.application_service.get_by_license_key(
            customer=customer, license_key=license_key)
        if application:
            _LOG.debug(f'Application associated with license {license_key} '
                       f'already exists: {application.application_id}. '
                       f'Execute license sync instead')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Application associated with license {license_key} '
                        f'already exists: {application.application_id}. '
                        f'Execute license sync instead'
            )

        description = event.get(DESCRIPTION_ATTR)
        if not description:
            _LOG.error('Description can\'t be empty.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Description can\'t be empty.'
            )

        _LOG.debug(f'Building application meta')
        app_meta = RightsizerLicensesApplicationMeta(
            license_key=license_key,
            tenant_license_key=tenant_license_key,
            cloud=cloud
        )

        _LOG.debug('Creating application')
        application = self.application_service.build(
            customer_id=customer_obj.name,
            type=RIGHTSIZER_LICENSES_TYPE,
            description=description,
            is_deleted=False,
            meta=app_meta.as_dict(),
            created_by=event.get(PARAM_USER_SUB)
        )
        _LOG.debug('Saving application')
        self.application_service.save(application=application)

        self._execute_license_sync(
            application=application
        )

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
        _LOG.debug(
            f'Searching for application {target_application.application_id} '
            f'parents')
        parents = self.parent_service.list_application_parents(
            application_id=target_application.application_id,
            only_active=True
        )
        force = event.get(FORCE_ATTR)
        try:
            if force:
                if parents:
                    _LOG.debug('Active linked parents found, deleting')
                    for parent in parents:
                        _LOG.debug(f'Force deleting parent {parent.parent_id}')
                        self.parent_service.force_delete(parent=parent)
                self.application_service.force_delete(
                    application=target_application)
            else:
                if parents:
                    active_parent_ids = [parent.parent_id for parent in
                                         parents]
                    message = (
                        f'Can\'t delete application with active parents: '
                        f'{", ".join(active_parent_ids)}')
                    _LOG.error(message)
                    return build_response(
                        code=RESPONSE_BAD_REQUEST_CODE,
                        content=message
                    )
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
        return license_key

    def _execute_license_sync(self, application):
        app_meta = self.application_service.get_application_meta(
            application=application
        )
        license_key = app_meta.license_key
        _LOG.info(f'Syncing license {license_key} '
                  f'in application {application.application_id}')
        response = self.license_manager_service.synchronize_license(
            license_key=license_key,
            customer=application.customer_id
        )
        if not response.status_code == 200:
            return

        license_data = response.json()['items'][0]

        _LOG.debug(f'Updating license {license_key}')
        application = self.application_service.update_license(
            application=application,
            license_data=license_data
        )
        _LOG.debug(f'Updating licensed algorithm')

        self.algorithm_service.sync_licensed_algorithm(
            license_data=license_data,
            customer=application.customer_id
        )
        return application

    @staticmethod
    def _is_allowed_customer(user_customer, customer):
        if user_customer == 'admin':
            return True
        if user_customer == customer:
            return True
        return False
