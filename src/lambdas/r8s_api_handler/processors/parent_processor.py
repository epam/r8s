from typing import List

from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, \
    TENANT_PARENT_MAP_RIGHTSIZER_TYPE, RIGHTSIZER_PARENT_TYPE
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    PARENT_ID_ATTR, APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    SCOPE_ATTR, \
    CLOUD_ALL, ALLOWED_PARENT_SCOPES, \
    PARENT_SCOPE_SPECIFIC_TENANT, TENANT_ATTR, CLOUDS_ATTR, PARENT_SCOPE_ALL
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.environment_service import EnvironmentService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-parent-processor')

CLOUDS = [AWS_CLOUD, AZURE_CLOUD, GOOGLE_CLOUD, CLOUD_ALL]


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
                                CLOUDS_ATTR, SCOPE_ATTR))
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

        clouds = event.get(CLOUDS_ATTR)
        clouds = list(set([cloud.upper() for cloud in clouds]))
        _LOG.debug(f'Validation clouds: {clouds}')
        if any([cloud not in CLOUDS for cloud in clouds]):
            _LOG.error(f'Some of the specified clouds are invalid. '
                       f'Available clouds: {", ".join(CLOUDS)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Some of the specified clouds are invalid. '
                        f'Available clouds: {", ".join(CLOUDS)}'
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
            if tenant_obj.cloud not in clouds:
                _LOG.error(f'{tenant_obj.cloud} tenant {tenant_obj.name} '
                           f'cannot be linked to {clouds} parent')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'{tenant_obj.cloud} tenant {tenant_obj.name} '
                            f'cannot be linked to {clouds} parent'
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
            scope=scope,
            clouds=clouds
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

        if scope and scope != PARENT_SCOPE_ALL:
            _LOG.debug(f'Describing tenants')
            clouds = parent_meta.clouds
            rate_limit = self.environment_service. \
                tenants_customer_name_index_rcu()
            for cloud in clouds:
                _LOG.debug(f'Describing linked {cloud} tenants')
                linked_tenants = self.parent_service.list_activated_tenants(
                    parent=parent,
                    cloud=cloud,
                    rate_limit=rate_limit
                )
                if linked_tenants:
                    message = f'There\'re tenants linked to parent ' \
                              f'\'{parent_id}\': ' \
                              f'{", ".join([t.name for t in linked_tenants])}'
                    _LOG.error(message)
                    return build_response(
                        code=RESPONSE_BAD_REQUEST_CODE,
                        content=message
                    )

        _LOG.debug(f'Deleting parent \'{parent.parent_id}\'')
        self.parent_service.mark_deleted(parent=parent)

        _LOG.debug(f'Saving parent: \'{parent.parent_id}\'')
        self.parent_service.save(parent=parent)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Parent \'{parent_id}\' has been deleted.'
        )
