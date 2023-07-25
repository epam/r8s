from typing import List

from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, \
    TENANT_PARENT_MAP_RIGHTSIZER_TYPE
from modular_sdk.models.parent import Parent
from modular_sdk.models.tenant import Tenant
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, PATCH_METHOD, \
    DELETE_METHOD, PARENT_ID_ATTR, APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    ALGORITHM_ATTR, CLOUD_ATTR, SCOPE_ATTR, \
    CLOUD_ALL, ALLOWED_PARENT_SCOPES, \
    PARENT_SCOPE_SPECIFIC_TENANT, TENANT_ATTR, TENANT_LICENSE_KEY_ATTR, \
    LICENSE_KEY_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.algorithm import Algorithm
from models.license import License
from services.algorithm_service import AlgorithmService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-parent-processor')

CLOUDS = [AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, CLOUD_ALL]


class ParentProcessor(AbstractCommandProcessor):
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
            PATCH_METHOD: self.patch,
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
        _LOG.debug(f'Describe parent event: {event}')

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
        _LOG.debug(f'Create parent event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR, DESCRIPTION_ATTR,
                                CLOUD_ATTR, SCOPE_ATTR))
        if not event.get(ALGORITHM_ATTR) and \
                not event.get(TENANT_LICENSE_KEY_ATTR):
            _LOG.error(f'One of the following parameters must be specified: '
                       f'{ALGORITHM_ATTR}, {TENANT_LICENSE_KEY_ATTR}')
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

        license_key = None
        tenant_license_key = event.get(TENANT_LICENSE_KEY_ATTR)
        if tenant_license_key:
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
        else:
            algorithm = event.get(ALGORITHM_ATTR)

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

        scope = event.get(SCOPE_ATTR).upper()

        if scope not in ALLOWED_PARENT_SCOPES:
            _LOG.error(f'Invalid value specified for \'{SCOPE_ATTR}\'. '
                       f'Allowed options: {", ".join(ALLOWED_PARENT_SCOPES)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid value specified for \'{SCOPE_ATTR}\'. '
                        f'Allowed options: {", ".join(ALLOWED_PARENT_SCOPES)}'
            )

        tenant_obj = None
        if scope == PARENT_SCOPE_SPECIFIC_TENANT:
            tenant_name = event.get(TENANT_ATTR)
            if not tenant_name:
                _LOG.error(f'Attribute \'{TENANT_ATTR}\' must be specified if '
                           f'\'{SCOPE_ATTR}\' attribute is set to '
                           f'\'{PARENT_SCOPE_SPECIFIC_TENANT}\'')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Attribute \'{TENANT_ATTR}\' must be specified '
                            f'if \'{SCOPE_ATTR}\' attribute is set to '
                            f'\'{PARENT_SCOPE_SPECIFIC_TENANT}\''
                )
            _LOG.debug(f'Describing tenant \'{tenant_name}\'')
            tenant_obj = self.tenant_service.get(tenant_name=tenant_name)
            if not tenant_obj:
                _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Tenant \'{tenant_name}\' does not exist.'
                )
            if cloud == CLOUD_ALL:
                _LOG.error(f'Can\'t set \'{CLOUD_ALL}\' clouds with specific '
                           f'tenant \'{tenant_name}\'')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Can\'t set \'{CLOUD_ALL}\' clouds with specific '
                            f'tenant \'{tenant_name}\''
                )
            if cloud != tenant_obj.cloud:
                _LOG.error(f'{tenant_obj.cloud} tenant {tenant_obj.name} '
                           f'cannot be linked to {cloud} parent')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'{tenant_obj.cloud} tenant {tenant_obj.name} '
                            f'cannot be linked to {cloud} parent'
                )

        description = event.get(DESCRIPTION_ATTR)
        if not description:
            _LOG.error('Description can\'t be empty.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Description can\'t be empty.'
            )

        _LOG.debug(f'Creating parent')
        parent = self.parent_service.create_rightsizer_parent(
            application_id=application.application_id,
            customer_id=customer,
            description=description,
            cloud=cloud,
            algorithm=algorithm_obj,
            scope=scope,
            license_key=license_key
        )

        parent_dto = self.parent_service.get_dto(parent=parent)
        _LOG.debug(f'Created parent \'{parent_dto}\'')

        if tenant_obj:
            try:
                _LOG.debug(f'Adding parent \'{parent.parent_id}\' to tenant '
                           f'\'{tenant_obj.name}\' parent map')
                self.tenant_service.add_to_parent_map(
                    tenant=tenant_obj,
                    parent=parent,
                    type_=TENANT_PARENT_MAP_RIGHTSIZER_TYPE
                )
            except ModularException as e:
                _LOG.error(e.content)
                return build_response(
                    code=e.code,
                    content=e.content
                )

        self.parent_service.save(parent=parent)
        _LOG.debug(f'Parent \'{parent.parent_id}\' has been saved')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=parent_dto
        )

    def patch(self, event):
        _LOG.debug(f'Update parent event: {event}')
        validate_params(event, (PARENT_ID_ATTR,))

        algorithm = event.get(ALGORITHM_ATTR)
        description = event.get(DESCRIPTION_ATTR)

        if not algorithm and not description:
            _LOG.error(f'You must specify either \'{ALGORITHM_ATTR}\' or '
                       f'\'{DESCRIPTION_ATTR}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'You must specify either \'{ALGORITHM_ATTR}\' or '
                        f'\'{DESCRIPTION_ATTR}\''
            )

        parent_id = event.get(PARENT_ID_ATTR)
        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)
        if not parent or parent.is_deleted:
            _LOG.error(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )

        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event)

        target_application = None
        for application in applications:
            if parent.application_id == application.application_id:
                target_application = application
                break
        if not target_application:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )

        if algorithm:
            _LOG.debug(f'Updating algorithm \'{algorithm}\'')
            algorithm_obj: Algorithm = self.algorithm_service.get_by_name(
                name=algorithm)
            if not algorithm_obj or algorithm_obj.customer != \
                    target_application.customer_id:
                _LOG.error(f'Algorithm \'{algorithm}\' does not exist.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Algorithm \'{algorithm}\' does not exist.'
                )
            parent_cloud = self.parent_service.get_parent_meta(parent).cloud
            if parent_cloud != CLOUD_ALL and \
                    parent_cloud != algorithm_obj.cloud.value:
                _LOG.error(f'Algorithm \'{algorithm}\' is not suitable for '
                           f'cloud \'{parent_cloud}\'. Algorithm\'s cloud: '
                           f'{algorithm_obj.cloud.value}')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Algorithm \'{algorithm}\' is not suitable for '
                            f'cloud \'{parent_cloud}\'. Algorithm\'s cloud: '
                            f'{algorithm_obj.cloud.value}'
                )
            self.parent_service.update_algorithm(parent=parent,
                                                 algorithm=algorithm_obj.name)

        description = event.get(DESCRIPTION_ATTR)
        if description:
            _LOG.debug(f'Updating description to \'{description}\'')
            parent.description = description

        _LOG.debug(f'Saving parent \'{parent_id}\'')

        self.parent_service.save(parent=parent)

        parent_dto = self.parent_service.get_dto(parent=parent)
        _LOG.debug(f"Response: {parent_dto}")

        return build_response(
            code=RESPONSE_OK_CODE,
            content=parent_dto
        )

    def delete(self, event):
        _LOG.debug(f'Delete parent event: {event}')
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

        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        scope = parent_meta.scope

        # todo temporary
        # if scope and scope != PARENT_SCOPE_ALL:
        #     _LOG.debug(f'Describing tenants')
        #     linked_tenant_names = self.get_linked_tenants(
        #         customer=parent.customer_id,
        #         parent_id=parent_id
        #     )
        #     if linked_tenant_names:
        #         _LOG.error(f'There\'re tenants linked to parent '
        #                    f'\'{parent_id}\': '
        #                    f'{", ".join(linked_tenant_names)}')
        #         return build_response(
        #             code=RESPONSE_BAD_REQUEST_CODE,
        #             content=f'There\'re tenants linked to parent '
        #                     f'\'{parent_id}\': '
        #                     f'{", ".join(linked_tenant_names)}'
        #         )

        _LOG.debug(f'Deleting parent \'{parent.parent_id}\'')
        self.parent_service.mark_deleted(parent=parent)

        _LOG.debug(f'Saving parent: \'{parent.parent_id}\'')
        self.parent_service.save(parent=parent)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Parent \'{parent_id}\' has been deleted.'
        )

    @staticmethod
    def _is_allowed_customer(user_customer, customer):
        if user_customer == 'admin':
            return True
        if user_customer == customer:
            return True
        return False

    def get_linked_tenants(self, customer: str, parent_id: str):
        _LOG.debug(f'Querying for customer '
                   f'\'{customer}\' tenants')
        tenants = self.tenant_service.i_get_tenant_by_customer(
            customer_id=customer,
            active=True,
            attributes_to_get=[Tenant.name, Tenant.parent_map]
        )
        linked_tenant_names = []

        for tenant in tenants:
            _LOG.debug(f'Processing tenant \'{tenant.name}\'')
            parent_map = tenant.parent_map.as_dict()
            if TENANT_PARENT_MAP_RIGHTSIZER_TYPE not in parent_map:
                _LOG.debug(f'Tenant \'{tenant.name}\' does not have linked '
                           f'RIGHTSIZER parent, skipping.')
                continue
            linked_parent_id = parent_map.get(
                TENANT_PARENT_MAP_RIGHTSIZER_TYPE)
            if parent_id == linked_parent_id:
                _LOG.debug(f'Tenant {tenant.name} is linked to target parent '
                           f'\'{parent_id}\'')
                linked_tenant_names.append(tenant.name)

        return linked_tenant_names

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
