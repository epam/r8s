from commons import RESPONSE_BAD_REQUEST_CODE, RESPONSE_FORBIDDEN_CODE, \
    raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, DELETE_METHOD, \
    PATCH_METHOD, USER_ID_ATTR, PASSWORD_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.clients.cognito import CUSTOM_ROLE_ATTR, CUSTOM_CUSTOMER_ATTR
from services.rbac.access_control_service import AccessControlService, \
    PARAM_TARGET_USER, PARAM_USER_CUSTOMER
from services.rbac.iam_service import IamService
from services.user_service import CognitoUserService

_LOG = get_logger('r8s-user-processor')


class UserProcessor(AbstractCommandProcessor):
    def __init__(self, user_service: CognitoUserService,
                 access_control_service: AccessControlService,
                 iam_service: IamService):
        self.user_service = user_service
        self.access_control_service = access_control_service
        self.iam_service = iam_service
        self.method_to_handler = {
            GET_METHOD: self.get,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'policy processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Get user event: {event}')

        target_user = event.get(PARAM_TARGET_USER)
        user_customer = event.get(PARAM_USER_CUSTOMER)

        attributes_to_get = [CUSTOM_ROLE_ATTR, CUSTOM_CUSTOMER_ATTR]
        if target_user:
            _LOG.debug(f'Extracting user with id \'{target_user}\'')
            users = [self.user_service.get_user(user_id=target_user)]
        elif user_customer == 'admin':
            _LOG.debug(f'Extracting all users')
            users = self.user_service.list_users(
                attributes_to_get=attributes_to_get)
        else:
            _LOG.debug(f'Extracting all users from customer '
                       f'\'{user_customer}\'')
            users = self.user_service.list_users(
                customer=user_customer, attributes_to_get=attributes_to_get)

        users = [user for user in users if user]

        if not users:
            _LOG.warning(f'No users found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No users found matching given query'
            )
        _LOG.debug(f'Response: {users}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=users
        )

    def patch(self, event):
        _LOG.debug(f'Update user event')
        validate_params(event, (PARAM_TARGET_USER, PASSWORD_ATTR))

        current_user_id = event.get(USER_ID_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)
        target_user = event.get(PARAM_TARGET_USER)
        target_user_customer = self.user_service.get_user_customer(target_user)

        allowed_to_update = self._is_allowed_to_modify(
            current_user_id=current_user_id,
            user_customer=user_customer,
            target_user_id=target_user,
            target_user_customer=target_user_customer
        )

        if not allowed_to_update:
            _LOG.error(f'You are not allowed to update user \'{target_user}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You are not allowed to update user \'{target_user}\''
            )

        password = event.get(PASSWORD_ATTR)

        _LOG.debug(f'Updating user \'{target_user}\' password')
        self.user_service.update_user_password(username=target_user,
                                               password=password)

        _LOG.debug(f'User with name \'{target_user}\' has been updated')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'User with name \'{target_user}\' has been updated'
        )

    def delete(self, event):
        _LOG.debug(f'Delete user event: {event}')
        validate_params(event, (PARAM_TARGET_USER,))

        current_user_id = event.get(USER_ID_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)
        target_user = event.get(PARAM_TARGET_USER)
        target_user_customer = self.user_service.get_user_customer(target_user)

        allowed_to_delete = self._is_allowed_to_modify(
            current_user_id=current_user_id,
            user_customer=user_customer,
            target_user_id=target_user,
            target_user_customer=target_user_customer
        )
        if not allowed_to_delete:
            _LOG.error(f'You are not allowed to delete user \'{target_user}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You are not allowed to delete user \'{target_user}\''
            )

        _LOG.debug(f'Describing user \'{target_user}\'')
        self.user_service.get_user(user_id=target_user)

        _LOG.debug(f'Deleting user \'{target_user}\'')
        self.user_service.delete_user(username=target_user)

        _LOG.debug(f'User with name \'{target_user}\' has been deleted')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'User with name \'{target_user}\' has been deleted'
        )

    @staticmethod
    def _is_allowed_to_modify(current_user_id, user_customer,
                              target_user_id, target_user_customer) -> bool:
        if user_customer == 'admin':
            # for admins, its allowed to delete every user except other admins
            return target_user_customer != 'admin'
        if current_user_id == target_user_id:
            # allow to delete self
            return True
        if user_customer == target_user_customer:
            # allow to delete user of same customer
            return True
        return False
