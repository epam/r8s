from modular_sdk.commons import ModularException
from modular_sdk.commons.constants import ApplicationType
from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, build_response, \
    RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE, secure_event
from commons.constants import (POST_METHOD, GET_METHOD, DELETE_METHOD,
                               CUSTOMER_ATTR, DESCRIPTION_ATTR,
                               APPLICATION_ID_ATTR, FORCE_ATTR,
                               CONNECTION_URL_ATTR, REQUEST_QUEUE_ATTR,
                               RESPONSE_QUEUE_ATTR, RABBIT_EXCHANGE_ATTR,
                               SDK_ACCESS_KEY_ATTR, SDK_SECRET_KEY_ATTR,
                               MAESTRO_USER_ATTR)
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-rabbitmq-application-processor')

RIGHTSIZER_RABBITMQ_TYPE = ApplicationType.RIGHTSIZER_RABBITMQ.value


class RabbitMQApplicationProcessor(AbstractCommandProcessor):
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

    @classmethod
    def build(cls):
        from services import SERVICE_PROVIDER
        return cls(
            application_service=SERVICE_PROVIDER.rightsizer_application_service(),
            parent_service=SERVICE_PROVIDER.rightsizer_parent_service(),
            customer_service=SERVICE_PROVIDER.customer_service()
        )

    def get(self, event):
        _LOG.debug(f'Describe rabbitmq application event: {event}')

        applications = self.application_service.resolve_application(
            event=event, type_=RIGHTSIZER_RABBITMQ_TYPE
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
        _LOG.debug(f'Create rabbitmq application event: {secure_event(event)}')
        validate_params(event, (CUSTOMER_ATTR, DESCRIPTION_ATTR,
                                CONNECTION_URL_ATTR, REQUEST_QUEUE_ATTR,
                                RESPONSE_QUEUE_ATTR, SDK_ACCESS_KEY_ATTR,
                                SDK_SECRET_KEY_ATTR, MAESTRO_USER_ATTR))

        description = event.get(DESCRIPTION_ATTR)
        if not description:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Attribute \'{DESCRIPTION_ATTR}\' can\'t be empty.'
            )

        customer = event.get(CUSTOMER_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)

        if not self._is_allowed_customer(user_customer=user_customer,
                                         customer=customer):
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You are not allowed to create application for '
                        f'customer \'{customer}\''
            )

        customer_obj = self.customer_service.get(name=customer)
        if not customer_obj:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Customer \'{customer}\' does not exist'
            )

        try:
            application = self.application_service.create_rabbitmq_application(
                customer_id=customer_obj.name,
                description=description,
                created_by=event.get(PARAM_USER_SUB),
                connection_url=event.get(CONNECTION_URL_ATTR),
                request_queue=event.get(REQUEST_QUEUE_ATTR),
                response_queue=event.get(RESPONSE_QUEUE_ATTR),
                rabbit_exchange=event.get(RABBIT_EXCHANGE_ATTR),
                sdk_access_key=event.get(SDK_ACCESS_KEY_ATTR),
                sdk_secret_key=event.get(SDK_SECRET_KEY_ATTR),
                maestro_user=event.get(MAESTRO_USER_ATTR),
            )
        except ModularException as e:
            _LOG.error(f'Exception occurred while creating application: '
                       f'{e.content}')
            return build_response(code=e.code, content=e.content)

        _LOG.debug(f'Saving application \'{application.application_id}\'')
        self.application_service.save(application=application)

        application_dto = self.application_service.get_dto(
            application=application)
        _LOG.debug(f'Response: {application_dto}')
        return build_response(code=RESPONSE_OK_CODE, content=application_dto)

    def delete(self, event):
        _LOG.debug(f'Delete rabbitmq application event: {event}')

        validate_params(event, (APPLICATION_ID_ATTR,))

        applications = self.application_service.resolve_application(
            event=event, type_=RIGHTSIZER_RABBITMQ_TYPE
        )
        application_id = event.get(APPLICATION_ID_ATTR)

        if not applications:
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Application with id \'{application_id}\' '
                        f'does not exist.'
            )

        application = applications[0]

        parents = self.parent_service.list_application_parents(
            application_id=application.application_id,
            only_active=True
        )
        if parents:
            _LOG.debug('Active linked parents found, deleting')
            for parent in parents:
                self.parent_service.mark_deleted(parent=parent)

        force = event.get(FORCE_ATTR)
        try:
            if force:
                self.application_service.force_delete(application=application)
            else:
                self.application_service.mark_deleted(application=application)
        except ModularException as e:
            return build_response(code=e.code, content=e.content)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Application \'{application.application_id}\' has been '
                    f'deleted.'
        )

    @staticmethod
    def _is_allowed_customer(user_customer, customer):
        if user_customer == 'admin':
            return True
        return user_customer == customer
