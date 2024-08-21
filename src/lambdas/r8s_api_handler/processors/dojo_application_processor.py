from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import ApplicationType
from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE, \
    secure_event
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, GET_METHOD, DELETE_METHOD, \
    CUSTOMER_ATTR, \
    DESCRIPTION_ATTR, PORT_ATTR, PROTOCOL_ATTR, HOST_ATTR, APPLICATION_ID_ATTR, \
    FORCE_ATTR, STAGE_ATTR, API_KEY_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-dojo-application-processor')


class DojoApplicationProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 customer_service: CustomerService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.customer_service = customer_service
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
                      f'dojo application processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe dojo application event: {event}')

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=ApplicationType.DEFECT_DOJO.value
        )

        if not applications:
            _LOG.warning('No application found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No application found matching given query.'
            )

        application_dtos = [self.application_service.get_dto(application)
                            for application in applications]
        _LOG.debug(f'Response: {application_dtos}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=application_dtos
        )

    def post(self, event):
        _LOG.debug(f'Create application event: {secure_event(event)}')
        validate_params(event, (CUSTOMER_ATTR, DESCRIPTION_ATTR,
                                HOST_ATTR, PORT_ATTR, PROTOCOL_ATTR,
                                STAGE_ATTR, API_KEY_ATTR))
        description = event.get(DESCRIPTION_ATTR)
        if not description:
            _LOG.error(f'Attribute \'{DESCRIPTION_ATTR}\' can\'t be empty.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Attribute \'{DESCRIPTION_ATTR}\' can\'t be empty.'
            )

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

        try:
            _LOG.debug('Creating application')
            application = (self.application_service.create_dojo_application(
                customer_id=customer_obj.name,
                description=description,
                created_by=event.get(PARAM_USER_SUB),
                host=event.get(HOST_ATTR),
                port=event.get(PORT_ATTR),
                protocol=event.get(PROTOCOL_ATTR),
                stage=event.get(STAGE_ATTR),
                api_key=event.get(API_KEY_ATTR)
            ))
        except ModularException as e:
            _LOG.error(f'Exception occurred while creating application: '
                       f'{e.content}')
            return build_response(
                code=e.code,
                content=e.content
            )

        _LOG.debug(f'Saving application '
                   f'\'{application.application_id}\'')
        self.application_service.save(application=application)

        _LOG.debug('Extracting created application dto')
        application_dto = self.application_service.get_dto(
            application=application)

        _LOG.debug(f'Response: {application_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=application_dto
        )

    def delete(self, event):
        _LOG.debug(f'Delete dojo application event: {event}')

        validate_params(event, (APPLICATION_ID_ATTR,))

        applications = self.application_service.resolve_application(
            event=event,
            type_=ApplicationType.DEFECT_DOJO.value
        )
        application_id = event.get(APPLICATION_ID_ATTR)

        if not applications:
            _LOG.warning(f'Application with id '
                         f'\'{application_id}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Application with id '
                        f'\'{application_id}\' does not exist.'
            )

        application = applications[0]

        _LOG.debug(f'Searching for application {application.application_id} '
                   f'parents')
        parents = self.parent_service.list_application_parents(
            application_id=application.application_id,
            only_active=True
        )
        if parents:
            _LOG.debug('Active linked parents found, deleting')
            for parent in parents:
                _LOG.debug(f'Deleting parent {parent.parent_id}')
                self.parent_service.mark_deleted(parent=parent)

        force = event.get(FORCE_ATTR)
        try:
            if force:
                self.application_service.force_delete(application=application)
            else:
                self.application_service.mark_deleted(application=application)
        except ModularException as e:
            return build_response(
                code=e.code,
                content=e.content
            )
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Application \'{application.application_id}\' has been '
                    f'deleted.'
        )

    @staticmethod
    def _is_allowed_customer(user_customer, customer):
        if user_customer == 'admin':
            return True
        if user_customer == customer:
            return True
        return False
