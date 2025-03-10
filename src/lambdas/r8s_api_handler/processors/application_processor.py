from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import ParentType, ParentScope
from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE, \
    RESPONSE_SERVICE_UNAVAILABLE_CODE, secure_event
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, GET_METHOD, PATCH_METHOD, \
    DELETE_METHOD, CUSTOMER_ATTR, \
    DESCRIPTION_ATTR, OUTPUT_STORAGE_ATTR, INPUT_STORAGE_ATTR, \
    CONNECTION_ATTR, PORT_ATTR, PROTOCOL_ATTR, HOST_ATTR, USERNAME_ATTR, \
    PASSWORD_ATTR, APPLICATION_ID_ATTR, MAESTRO_RIGHTSIZER_APPLICATION_TYPE, \
    FORCE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.application_attributes import ConnectionAttribute
from models.storage import Storage, StorageTypeEnum
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER, \
    PARAM_USER_ID
from services.algorithm_service import AlgorithmService
from services.clients.api_gateway_client import ApiGatewayClient
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.storage_service import StorageService

_LOG = get_logger('r8s-application-processor')

DEFAULT_CONNECTION = {
    PORT_ATTR: 443,
    PROTOCOL_ATTR: 'HTTPS'
}


class ApplicationProcessor(AbstractCommandProcessor):
    def __init__(self, algorithm_service: AlgorithmService,
                 storage_service: StorageService,
                 customer_service: CustomerService,
                 application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 api_gateway_client: ApiGatewayClient):
        self.algorithm_service = algorithm_service
        self.storage_service = storage_service
        self.customer_service = customer_service
        self.application_service = application_service
        self.api_gateway_client = api_gateway_client
        self.parent_service = parent_service
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
        _LOG.debug(f'Describe application event: {event}')

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
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
                                INPUT_STORAGE_ATTR, OUTPUT_STORAGE_ATTR,
                                CONNECTION_ATTR))
        description = event.get(DESCRIPTION_ATTR)
        if not description:
            _LOG.error(f'Attribute \'{DESCRIPTION_ATTR}\' can\'t be empty.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Attribute \'{DESCRIPTION_ATTR}\' can\'t be empty.'
            )

        connection = event.get(CONNECTION_ATTR)
        _LOG.debug(f'Validating connection \'{connection}\'')
        if not isinstance(connection, dict):
            _LOG.error(f'\'{CONNECTION_ATTR}\' attribute must be a valid '
                       f'dict.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{CONNECTION_ATTR}\' attribute must be a valid '
                        f'dict.'
            )
        connection = {**DEFAULT_CONNECTION, **connection}
        validate_params(connection, (PORT_ATTR, PROTOCOL_ATTR,
                                     USERNAME_ATTR, PASSWORD_ATTR))
        if not connection.get(HOST_ATTR):
            _LOG.debug(f'\'{HOST_ATTR}\' is not specified and will be '
                       f'resolved automatically')
            r8s_host = self.api_gateway_client.get_r8s_api_host()
            if not r8s_host:
                _LOG.error('No RightSizer API found. Please contact '
                           'the support team.')
                return build_response(
                    code=RESPONSE_SERVICE_UNAVAILABLE_CODE,
                    content='No RightSizer API found. Please contact '
                            'the support team.'
                )
            _LOG.debug(f'Setting host \'{r8s_host}\' into connection')
            connection[HOST_ATTR] = r8s_host

        customer = event.get(CUSTOMER_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)
        user_id = event.get(PARAM_USER_ID)

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

        input_storage = event.get(INPUT_STORAGE_ATTR)
        _LOG.debug(f'Validating input storage \'{input_storage}\'')
        input_storage_obj = self.storage_service.get_by_name(
            name=input_storage)

        self._validate_storage(
            storage_name=input_storage,
            storage=input_storage_obj,
            required_type=StorageTypeEnum.DATA_SOURCE.value
        )

        output_storage = event.get(OUTPUT_STORAGE_ATTR)
        _LOG.debug(f'Validating output storage \'{output_storage}\'')
        output_storage_obj = self.storage_service.get_by_name(
            name=output_storage)
        self._validate_storage(
            storage_name=output_storage,
            storage=output_storage_obj,
            required_type=StorageTypeEnum.STORAGE.value
        )

        password = connection.pop(PASSWORD_ATTR, None)
        connection_obj = ConnectionAttribute(**connection)
        try:
            _LOG.debug('Creating application')
            application = self.application_service. \
                create_rightsizer_application(
                customer_id=customer,
                description=description,
                input_storage=input_storage_obj,
                output_storage=output_storage_obj,
                connection=connection_obj,
                password=password,
                created_by=event.get(PARAM_USER_SUB)
            )
        except ModularException as e:
            _LOG.error(f'Exception occurred while creating application: '
                       f'{e.content}')
            return build_response(
                code=e.code,
                content=e.content
            )

        _LOG.debug('Creating RIGHTSIZER parent with ALL scope')
        parent = self.parent_service.build(
            application_id=application.application_id,
            customer_id=application.customer_id,
            parent_type=ParentType.RIGHTSIZER_PARENT,
            description='Automatically created RIGHTSIZER parent',
            meta={},
            scope=ParentScope.ALL,
            created_by=user_id
        )

        _LOG.debug(f'Saving application '
                   f'\'{application.application_id}\'')
        self.application_service.save(application=application)

        _LOG.debug(f'Saving parent: {parent.parent_id}')
        self.parent_service.save(parent=parent)

        _LOG.debug('Extracting created application dto')
        application_dto = self.application_service.get_dto(
            application=application)

        _LOG.debug(f'Response: {application_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=application_dto
        )

    def patch(self, event):
        _LOG.debug(f'Update job definition event: {secure_event(event)}')

        validate_params(event, (APPLICATION_ID_ATTR,))

        applications = self.application_service.resolve_application(
            event=event,
            type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
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
        application_meta = self.application_service.get_application_meta(
            application=application
        )
        input_storage = event.get(INPUT_STORAGE_ATTR)
        input_storage_obj = None
        if input_storage:
            _LOG.debug(f'Validating input storage \'{input_storage}\'')
            input_storage_obj = self.storage_service.get_by_name(
                name=input_storage)

            self._validate_storage(
                storage_name=input_storage,
                storage=input_storage_obj,
                required_type=StorageTypeEnum.DATA_SOURCE.value
            )

        output_storage = event.get(OUTPUT_STORAGE_ATTR)
        output_storage_obj = None
        if output_storage:
            _LOG.debug(f'Validating output storage \'{output_storage}\'')
            output_storage_obj = self.storage_service.get_by_name(
                name=output_storage)
            self._validate_storage(
                storage_name=output_storage,
                storage=output_storage_obj,
                required_type=StorageTypeEnum.STORAGE.value
            )

        connection = event.get(CONNECTION_ATTR)
        connection_obj = None
        password = None
        if connection:
            _LOG.debug(f'Validating connection \'{connection}\'')
            if not isinstance(connection, dict):
                _LOG.error(f'\'{CONNECTION_ATTR}\' attribute must be a valid '
                           f'dict.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'\'{CONNECTION_ATTR}\' attribute must be a valid '
                            f'dict.'
                )
            connection = {**application_meta.connection.as_dict(),
                          **connection}
            password = connection.pop(PASSWORD_ATTR, None)
            connection_obj = ConnectionAttribute(**connection)

        description = None
        if DESCRIPTION_ATTR in event:
            description = event.get(DESCRIPTION_ATTR)

            if not isinstance(description, str):
                _LOG.error(f'Attribute \'{DESCRIPTION_ATTR}\' '
                           f'must be a string.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Attribute \'{DESCRIPTION_ATTR}\' '
                            f'must be a string.'
                )
            if not description:
                _LOG.error(f'Description must not be empty.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Description must not be empty.'
                )

        _LOG.debug(f'Updating application \'{application.application_id}\'')
        self.application_service.update_rightsizer_application(
            application=application,
            description=description,
            input_storage=input_storage_obj,
            output_storage=output_storage_obj,
            connection=connection_obj,
            password=password,
            updated_by=event.get(PARAM_USER_SUB)
        )

        application_dto = self.application_service.get_dto(
            application=application)
        _LOG.debug(f'Response: {application_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=application_dto
        )

    def delete(self, event):
        _LOG.debug(f'Delete application event: {event}')

        validate_params(event, (APPLICATION_ID_ATTR,))

        applications = self.application_service.resolve_application(
            event=event,
            type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
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
    def _validate_storage(storage_name: str, storage: Storage,
                          required_type):
        if not storage:
            _LOG.debug(f'Storage with name \'{storage_name}\' '
                       f'does not exist')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Storage with name \'{storage_name}\' '
                        f'does not exist'
            )
        if storage.type.value != required_type:
            _LOG.debug(f'Storage \'{storage_name}\' must have '
                       f'\'{required_type}\' type.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Storage \'{storage_name}\' must have '
                        f'\'{required_type}\' type.'
            )

    @staticmethod
    def _is_allowed_customer(user_customer, customer):
        if user_customer == 'admin':
            return True
        if user_customer == customer:
            return True
        return False
