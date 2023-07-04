from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import TENANT_PARENT_MAP_RIGHTSIZER_TYPE
from modular_sdk.models.tenant import Tenant
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, \
    RESPONSE_FORBIDDEN_CODE, validate_params, RESPONSE_OK_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, DELETE_METHOD, PARENT_ID_ATTR, \
    TENANT_ATTR, PARENT_SCOPE_SPECIFIC_TENANT, GET_METHOD, TENANTS_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-parent-tenant-linkage-processor')


class ParentTenantLinkageProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service

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
        _LOG.debug(f'Describe linked tenants event: {event}')
        validate_params(event, (PARENT_ID_ATTR,))

        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event
        )

        if not applications:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )
        allowed_application_ids = [app.application_id for app in applications]
        _LOG.debug(f'Allowed applications for user '
                   f'\'{", ".join(allowed_application_ids)}\'')
        parent_id = event.get(PARENT_ID_ATTR)
        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)

        if not parent or parent.application_id not in allowed_application_ids:
            _LOG.error(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )
        target_application = [app for app in applications if
                              app.application_id == parent.application_id][0]
        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        if not parent_meta or parent_meta.scope != \
                PARENT_SCOPE_SPECIFIC_TENANT:
            _LOG.error(f'Parent \'{parent_id}\' scope must be set to '
                       f'\'{PARENT_SCOPE_SPECIFIC_TENANT}\'.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent \'{parent_id}\' scope must be set to '
                        f'\'{PARENT_SCOPE_SPECIFIC_TENANT}\'.'
            )
        _LOG.debug(f'Querying for customer '
                   f'\'{target_application.customer_id}\' tenants')
        tenants = self.tenant_service.i_get_tenant_by_customer(
            customer_id=target_application.customer_id,
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

        if not linked_tenant_names:
            _LOG.error(f'Parent \'{parent_id}\' does not have linked tenants.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent_id}\' does not have linked tenants.'
            )
        _LOG.debug(f'Found linked tenants: {", ".join(linked_tenant_names)}')

        response = {
            PARENT_ID_ATTR: parent_id,
            TENANTS_ATTR: linked_tenant_names
        }
        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event):
        _LOG.debug(f'Link tenant to parent event: {event}')
        validate_params(event, (PARENT_ID_ATTR, TENANT_ATTR))

        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event
        )

        if not applications:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )
        allowed_application_ids = [app.application_id for app in applications]
        _LOG.debug(f'Allowed applications for user '
                   f'\'{", ".join(allowed_application_ids)}\'')
        parent_id = event.get(PARENT_ID_ATTR)
        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)

        if not parent or parent.application_id not in allowed_application_ids:
            _LOG.error(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )

        tenant_name = event.get(TENANT_ATTR)
        tenant = self.tenant_service.get(tenant_name=tenant_name)

        if not tenant:
            _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Tenant \'{tenant_name}\' does not exist.'
            )
        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        if parent_meta.scope != PARENT_SCOPE_SPECIFIC_TENANT:
            _LOG.error(f'Parent \'{parent_id}\' scope must be set to '
                       f'\'{PARENT_SCOPE_SPECIFIC_TENANT}\' to link tenants.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent \'{parent_id}\' scope must be set to '
                        f'\'{PARENT_SCOPE_SPECIFIC_TENANT}\' to link tenants.'
            )
        if parent_meta.cloud != tenant.cloud:
            _LOG.error(f'{tenant.cloud} tenant {tenant.name} cannot be '
                       f'linked to {parent_meta.cloud} parent \'{parent_id}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'{tenant.cloud} tenant {tenant.name} cannot be '
                        f'linked to {parent_meta.cloud} parent \'{parent_id}\''
            )
        try:
            _LOG.debug(f'Adding Parent \'{parent.parent_id}\' to tenant '
                       f'\'{tenant_name}\' parent map')
            self.tenant_service.add_to_parent_map(
                tenant=tenant,
                parent=parent,
                type_=TENANT_PARENT_MAP_RIGHTSIZER_TYPE
            )
        except ModularException as e:
            _LOG.error(f'Exception occurred while adding parent '
                       f'\'{parent.parent_id}\' to tenant \'{tenant_name}\' '
                       f'parent map: {e.content}')
            return build_response(
                code=e.code,
                content=e.content
            )

        _LOG.debug(f'Parent \'{parent_id}\' has been added to tenant '
                   f'{tenant_name} parent map.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Parent \'{parent_id}\' has been added to tenant '
                    f'{tenant_name} parent map.'
        )

    def delete(self, event):
        _LOG.debug(f'Unlink RIGHTSIZER parent from tenant event: {event}')
        validate_params(event, (TENANT_ATTR,))

        user_customer = event.get(PARAM_USER_CUSTOMER)
        tenant_name = event.get(TENANT_ATTR)
        tenant = self.tenant_service.get(tenant_name=tenant_name)

        if not tenant:
            _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Tenant \'{tenant_name}\' does not exist.'
            )
        if user_customer != 'admin' and tenant.customer_name != user_customer:
            _LOG.error(f'User is not allowed to affect customer '
                       f'\'{tenant.customer_name}\'.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You are not allowed to affect customer '
                        f'\'{tenant.customer_name}\''
            )

        parent_map = tenant.parent_map

        if parent_map:
            parent_map = parent_map.as_dict()
        if not parent_map or TENANT_PARENT_MAP_RIGHTSIZER_TYPE \
                not in parent_map:
            _LOG.error(f'Tenant \'{tenant_name}\' does not have linked '
                       f'{TENANT_PARENT_MAP_RIGHTSIZER_TYPE} parent.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Tenant \'{tenant_name}\' does not have linked '
                        f'{TENANT_PARENT_MAP_RIGHTSIZER_TYPE} parent.'
            )

        try:
            _LOG.debug(f'Removing RIGHTSIZER parent linkage from tenant '
                       f'\'{tenant_name}\' parent map')
            self.tenant_service.remove_from_parent_map(
                tenant=tenant,
                type_=TENANT_PARENT_MAP_RIGHTSIZER_TYPE
            )
        except ModularException as e:
            _LOG.error(f'Exception occurred while removing RIGHTSIZER parent '
                       f'linkage from tenant \'{tenant_name}\' '
                       f'parent map: {e.content}')
            return build_response(
                code=e.code,
                content=e.content
            )
        _LOG.debug(f'RIGHTSIZER parent link has been removed from tenant '
                   f'\'{tenant_name}\'.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'RIGHTSIZER parent link has been removed from tenant '
                    f'\'{tenant_name}\'.'
        )
