from typing import List

from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, \
    RIGHTSIZER_LICENSES_PARENT_TYPE, \
    TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE, ParentScope
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    PARENT_ID_ATTR, APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    CLOUD_ATTR, CLOUD_ALL, PARENT_SCOPE_SPECIFIC_TENANT, \
    TENANT_LICENSE_KEY_ATTR, \
    LICENSE_KEY_ATTR, PARENT_SCOPE_ALL
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.algorithm import Algorithm
from models.license import License
from models.parent_attributes import LicensesParentMeta
from services.algorithm_service import AlgorithmService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-parent-licenses-processor')

CLOUDS = [AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, CLOUD_ALL]


class ParentLicensesProcessor(AbstractCommandProcessor):
    def __init__(self, algorithm_service: AlgorithmService,
                 customer_service: CustomerService,
                 application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService,
                 license_service: LicenseService,
                 license_manager_service: LicenseManagerService):
        self.algorithm_service = algorithm_service
        self.customer_service = customer_service
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service
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
        _LOG.debug(f'Describe parent licenses event: {event}')

        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event)

        if not applications:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )

        parents: List[Parent] = []

        for application in applications:
            application_parents = self.parent_service.list_application_parents(
                application_id=application.application_id,
                type_=RIGHTSIZER_LICENSES_PARENT_TYPE,
                only_active=True
            )
            _LOG.debug(f'Got \'{len(application_parents)}\' from application '
                       f'\'{application.application_id}\'')
            parents.extend(application_parents)

        parent_id = event.get(PARENT_ID_ATTR)
        if parent_id:
            parents = [parent for parent in parents if
                       parent.parent_id == parent_id]
        if not parents:
            _LOG.error(f'No Parents found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No Parents found matching given query.'
            )

        response = [self.parent_service.get_dto(parent) for parent in parents]
        _LOG.debug(f'Response: {response}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event):
        _LOG.debug(f'Create licensed parent event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR, DESCRIPTION_ATTR,
                                CLOUD_ATTR, TENANT_LICENSE_KEY_ATTR))

        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event)

        if not applications:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )
        if len(applications) > 1:
            _LOG.error(f'Exactly one application must be identified.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Exactly one application must be identified.'
            )
        application = applications[0]
        _LOG.debug(f'Target application \'{application.application_id}\'')

        customer = application.customer_id
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
        algorithm = license_obj.algorithm_id

        _LOG.debug(f'Validating algorithm \'{algorithm}\'')
        algorithm_obj: Algorithm = self.algorithm_service.get_by_name(
            name=algorithm)
        if not algorithm_obj or algorithm_obj.customer != customer:
            _LOG.error(f'Algorithm \'{algorithm}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm}\' does not exist.'
            )
        if cloud != CLOUD_ALL and cloud != algorithm_obj.cloud.value:
            _LOG.error(f'Algorithm \'{algorithm}\' is not suitable for '
                       f'cloud \'{cloud}\'. Algorithm\'s cloud: '
                       f'{algorithm_obj.cloud.value}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm}\' is not suitable for '
                        f'cloud \'{cloud}\'. Algorithm\'s cloud: '
                        f'{algorithm_obj.cloud.value}'
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
            customer=application.customer_id
        )
        if tenants is None:  # license activation is forbidden
            _LOG.error(f'Activation of license \'{license_obj.license_key}\' '
                       f'is forbidden to customer '
                       f'\'{application.customer_id}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'Activation of license \'{license_obj.license_key}\' '
                        f'is forbidden to customer '
                        f'\'{application.customer_id}\''
            )

        meta = LicensesParentMeta(
            cloud=cloud,
            algorithm=algorithm.name,
            license_key=license_key,
        )
        parents = []
        for index, tenant in enumerate(tenants, start=1):
            _LOG.debug(f'{index}/{len(tenants)} Creating RIGHTSIZER_LICENSES '
                       f'parent for tenant {tenant}')
            parent = self.parent_service.create_tenant_scope(
                application_id=application.application_id,
                customer_id=customer,
                type_=RIGHTSIZER_LICENSES_PARENT_TYPE,
                description=description,
                meta=meta.as_dict(),
                tenant_name=tenant
            )
            parents.append(parent)
        else:
            _LOG.debug(f'Creating RIGHTSIZER_LICENSES parent for all tenants '
                       f'in cloud: {cloud}')
            parent = self.parent_service.create_all_scope(
                application_id=application.application_id,
                customer_id=customer,
                type_=RIGHTSIZER_LICENSES_PARENT_TYPE,
                description=description,
                meta=meta.as_dict(),
                cloud=cloud
            )
            parents.append(parent)

        _LOG.debug(f'Going to save {len(parents)} parent(s).')
        for parent in parents:
            self.parent_service.save(parent=parent)

        parent_dtos = [self.parent_service.get_dto(parent=parent)
                       for parent in parents]
        _LOG.debug(f'Created parents: \'{parent_dtos}\'')

        for parent in parents:
            if not parent.tenant_name:
                continue
            try:
                _LOG.debug(f'Going to activate tenants {tenants} for parent '
                           f'\'{parent.parent_id}\'')
                self.activate_tenant(
                    tenant_name=parent.tenant_name,
                    parent=parent
                )
            except ModularException as e:
                _LOG.error(e.content)
                return build_response(
                    code=e.code,
                    content=e.content
                )

        return build_response(
            code=RESPONSE_OK_CODE,
            content=parent_dtos
        )

    def delete(self, event):
        _LOG.debug(f'Delete licenses parent event: {event}')
        validate_params(event, (PARENT_ID_ATTR,))

        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event)

        if not applications:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )
        app_ids = [app.application_id for app in applications]
        _LOG.debug(f'Allowed application ids \'{app_ids}\'')

        parent_id = event.get(PARENT_ID_ATTR)
        _LOG.debug(f'Describing parent by id \'{parent_id}\'')
        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)
        if not parent or parent.is_deleted or parent.application_id \
                not in app_ids:
            _LOG.debug(f'Parent \'{parent_id}\' does not exist or '
                       f'already deleted.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent_id}\' does not exist or '
                        f'already deleted.'
            )

        if parent.tenant_name:
            _LOG.debug(f'Describing tenant {parent.tenant_name}')
            tenant = self.tenant_service.get(tenant_name=parent.tenant_name)
            if not tenant:
                _LOG.warning(f'Linked tenant {parent.tenant_name} '
                             f'does not exist.')
            else:
                _LOG.debug(f'Going to unlink tenant {parent.tenant_name} '
                           f'from parent {parent.parent_id}')
                self.tenant_service.remove_from_parent_map(
                    tenant=tenant,
                    type_=RIGHTSIZER_LICENSES_PARENT_TYPE
                )

        _LOG.debug(f'Deleting parent \'{parent.parent_id}\'')
        self.parent_service.mark_deleted(parent=parent)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Parent \'{parent_id}\' has been deleted.'
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
            license_key=license_obj.license_key)
        if not response.status_code == 200:
            return

        license_data = response.json()['items'][0]

        _LOG.debug(f'Updating license {license_obj.license_key}')
        license_obj = self.license_service.update_license(
            license_obj=license_obj,
            license_data=license_data
        )
        _LOG.debug(f'Updating licensed algorithm')
        self.algorithm_service.sync_licensed_algorithm(
            license_data=license_data,
            customer=customer
        )
        return license_obj

    def activate_tenant(self, tenant_name: str, parent: Parent):
        _LOG.debug(f'Describing tenant \'{tenant_name}\'')
        tenant_obj = self.tenant_service.get(tenant_name=tenant_name)
        if not tenant_obj:
            _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Tenant \'{tenant_name}\' does not exist.'
            )
        self.tenant_service.add_to_parent_map(
            tenant=tenant_obj,
            parent=parent,
            type_=TENANT_PARENT_MAP_RIGHTSIZER_LICENSES_TYPE
        )
