from typing import List

from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import (TENANT_PARENT_MAP_RIGHTSIZER_TYPE,
                                           RIGHTSIZER_PARENT_TYPE, ParentScope)
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    PARENT_ID_ATTR, APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    SCOPE_ATTR, TENANT_ATTR, CLOUD_ATTR, CLOUDS
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.environment_service import EnvironmentService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-parent-processor')


class ParentProcessor(AbstractCommandProcessor):
    def __init__(self, customer_service: CustomerService,
                 application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService,
                 environment_service: EnvironmentService):
        self.customer_service = customer_service
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service
        self.environment_service = environment_service

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
                type_=RIGHTSIZER_PARENT_TYPE,
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
                                SCOPE_ATTR))
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

        scope = event.get(SCOPE_ATTR).upper()

        if scope not in list(ParentScope):
            _LOG.error(f'Invalid value specified for \'{SCOPE_ATTR}\'. '
                       f'Allowed options: {", ".join(list(ParentScope))}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid value specified for \'{SCOPE_ATTR}\'. '
                        f'Allowed options: {", ".join(list(ParentScope))}'
            )

        tenant_obj = None
        tenant_name = event.get(TENANT_ATTR)
        if scope != ParentScope.ALL.value:
            if not tenant_name:
                _LOG.error(f'Attribute \'{TENANT_ATTR}\' must be specified if '
                           f'\'{SCOPE_ATTR}\' attribute is set to '
                           f'\'{ParentScope.ALL.value}\'')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Attribute \'{TENANT_ATTR}\' must be specified '
                            f'if \'{SCOPE_ATTR}\' attribute is set to '
                            f'\'{ParentScope.ALL.value}\''
                )
            _LOG.debug(f'Describing tenant \'{tenant_name}\'')
            tenant_obj = self.tenant_service.get(tenant_name=tenant_name)
            if not tenant_obj:
                _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Tenant \'{tenant_name}\' does not exist.'
                )
        elif tenant_name:
            _LOG.error(f'\'{TENANT_ATTR}\' attribute must not be used with '
                       f'{ParentScope.ALL.value} scope')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{TENANT_ATTR}\' attribute must not be used with '
                        f'{ParentScope.ALL.value} scope'
            )

        cloud = event.get(CLOUD_ATTR)
        if cloud:
            _LOG.debug(f'Validation cloud: {cloud}')
            if cloud not in CLOUDS:
                _LOG.error(f'Some of the specified clouds are invalid. '
                           f'Available clouds: {", ".join(CLOUDS)}')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Some of the specified clouds are invalid. '
                            f'Available clouds: {", ".join(CLOUDS)}'
                )
        if cloud and scope != ParentScope.ALL.value:
            _LOG.error(f'Parent cloud can only be used with '
                       f'{ParentScope.ALL.value} Parent scope')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent cloud can only be used with '
                        f'{ParentScope.ALL.value} Parent scope'
            )

        description = event.get(DESCRIPTION_ATTR)
        if not description:
            _LOG.error('Description can\'t be empty.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Description can\'t be empty.'
            )

        _LOG.debug(f'Creating parent')
        parent = self.parent_service.create(
            application_id=application.application_id,
            customer_id=customer,
            parent_type=RIGHTSIZER_PARENT_TYPE,
            description=description,
            meta={},
            scope=scope,
            cloud=cloud,
            tenant_name=tenant_obj.name if tenant_obj else None
        )

        parent_dto = self.parent_service.get_dto(parent=parent)
        _LOG.debug(f'Created parent \'{parent_dto}\'')

        if tenant_obj:
            try:
                _LOG.debug(f'Adding parent \'{parent.parent_id}\' to tenant '
                           f'\'{tenant_obj.name}\' parent map')
                # self.tenant_service.add_to_parent_map(
                #     tenant=tenant_obj,
                #     parent=parent,
                #     type_=TENANT_PARENT_MAP_RIGHTSIZER_TYPE
                # )
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

        if parent.scope and parent.scope != ParentScope.ALL.value:
            _LOG.debug(f'Describing linked tenants')

            _LOG.debug(f'Describing linked tenant {parent.tenant_name}')
            tenant = self.tenant_service.get(
                tenant_name=parent.tenant_name)
            if not tenant:
                _LOG.warning(f'Linked tenant {parent.tenant_name} '
                             f'does not exist.')
            else:
                _LOG.debug(f'Unlinking tenant {tenant.name} from parent '
                           f'{parent.parent_id}')
                self.tenant_service.remove_from_parent_map(
                    tenant=tenant,
                    type_=RIGHTSIZER_PARENT_TYPE
                )

        _LOG.debug(f'Deleting parent \'{parent.parent_id}\'')
        self.parent_service.mark_deleted(parent=parent)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Parent \'{parent_id}\' has been deleted.'
        )
