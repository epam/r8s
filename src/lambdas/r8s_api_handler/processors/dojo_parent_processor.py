from typing import List

from modular_sdk.commons.constants import ParentType, ApplicationType, \
    ParentScope
from modular_sdk.models.parent import Parent
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    PARENT_ID_ATTR, APPLICATION_ID_ATTR, DESCRIPTION_ATTR, \
    SCOPE_ATTR, TENANT_ATTR, FORCE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.parent_attributes import DojoParentMeta
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-dojo-parent-processor')


class DojoParentProcessor(AbstractCommandProcessor):
    def __init__(self, customer_service: CustomerService,
                 application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService):
        self.customer_service = customer_service
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
                      f'dojo parent processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe dojo parent event: {event}')

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=ApplicationType.DEFECT_DOJO.value)

        if not applications:
            _LOG.warning('No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No application found matching given query.'
            )

        parents: List[Parent] = []

        for application in applications:
            application_parents = self.parent_service.list_application_parents(
                application_id=application.application_id,
                only_active=True
            )
            if not application_parents:
                continue
            application_parents = [
                parent for parent in application_parents if
                parent.type == ParentType.RIGHTSIZER_SIEM_DEFECT_DOJO.value
            ]
            _LOG.debug(f'Got \'{len(application_parents)}\' from application '
                       f'\'{application.application_id}\'')
            parents.extend(application_parents)

        parent_id = event.get(PARENT_ID_ATTR)
        if parent_id:
            parents = [parent for parent in parents if
                       parent.parent_id == parent_id]
        if not parents:
            _LOG.error('No Parents found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No Parents found matching given query.'
            )

        response = [self.parent_service.get_dto(parent) for parent in parents]
        _LOG.debug(f'Response: {response}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event):
        _LOG.debug(f'Create licensed parent event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR,
                                DESCRIPTION_ATTR, SCOPE_ATTR))

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=ApplicationType.DEFECT_DOJO)

        if not applications:
            _LOG.warning('No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No application found matching given query.'
            )
        if len(applications) > 1:
            _LOG.error('Exactly one application must be identified.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Exactly one application must be identified.'
            )
        application = applications[0]
        _LOG.debug(f'Target application \'{application.application_id}\'')

        scope = event.get(SCOPE_ATTR)
        scope_options = [i.value for i in ParentScope]
        if scope not in scope_options:
            _LOG.error(f'Invalid parent scope specified: {scope}. '
                       f'Valid options: {scope_options}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid parent scope specified: {scope}. '
                        f'Valid options: {scope_options}'
            )
        tenant_name = event.get(TENANT_ATTR)
        if scope == ParentScope.SPECIFIC.value and not tenant_name:
            _LOG.error(f'\'{TENANT_ATTR}\' attr required for '
                       f'\'{ParentScope.SPECIFIC.value}\' parent scope.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{TENANT_ATTR}\' attr required for '
                        f'\'{ParentScope.SPECIFIC.value}\' parent scope.'
            )

        meta = DojoParentMeta.build()

        _LOG.debug('Creating parent')
        parent = self.parent_service.build(
            application_id=application.application_id,
            customer_id=application.customer_id,
            parent_type=ParentType.RIGHTSIZER_SIEM_DEFECT_DOJO,
            is_deleted=False,
            description=event.get(DESCRIPTION_ATTR),
            meta=meta.as_dict(),
            scope=scope,
            tenant_name=tenant_name,
            created_by=event.get(PARAM_USER_SUB)
        )

        _LOG.debug('Saving parent')
        self.parent_service.save(parent=parent)

        _LOG.debug('Preparing response')
        response = self.parent_service.get_dto(parent=parent)

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def delete(self, event):
        _LOG.debug(f'Delete dojo parent event: {event}')
        validate_params(event, (PARENT_ID_ATTR,))

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=ApplicationType.DEFECT_DOJO)

        if not applications:
            _LOG.warning('No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No application found matching given query.'
            )
        app_ids = [app.application_id for app in applications]
        _LOG.debug(f'Allowed application ids \'{app_ids}\'')

        parent_id = event.get(PARENT_ID_ATTR)
        force = event.get(FORCE_ATTR)
        _LOG.debug(f'Describing parent by id \'{parent_id}\'')
        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)

        if not parent or parent.application_id not in app_ids:
            _LOG.debug(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )

        if force:
            self.parent_service.force_delete(parent=parent)
        elif parent.is_deleted:
            _LOG.debug(f'Parent {parent.parent_id} already marked as deleted')
            return build_response(
                code=RESPONSE_OK_CODE,
                content=f'Parent {parent.parent_id} already marked as deleted'
            )
        else:
            self.parent_service.mark_deleted(parent=parent)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Parent \'{parent_id}\' has been deleted.'
        )
