from commons import RESPONSE_BAD_REQUEST_CODE, build_response, RESPONSE_OK_CODE
from commons.constants import POST_METHOD, USERNAME_ATTR, PASSWORD_ATTR, \
    ROLES_ATTR, CUSTOMER_ATTR, TENANTS_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rbac.access_control_service import AccessControlService
from services.user_service import CognitoUserService

_LOG = get_logger('r8s-signup-processor')


class SignUpProcessor(AbstractCommandProcessor):
    def __init__(self, user_service: CognitoUserService,
                 access_control_service: AccessControlService):
        self.user_service = user_service
        self.access_control_service = access_control_service
        self.method_to_handler = {
            POST_METHOD: self.post,
        }

    @classmethod
    def build(cls):
        from services import SERVICE_PROVIDER
        return cls(
            user_service=SERVICE_PROVIDER.user_service(),
            access_control_service=SERVICE_PROVIDER.access_control_service()
        )

    def post(self, event):
        username = event.get(USERNAME_ATTR)
        password = event.get(PASSWORD_ATTR)
        roles = event.get(ROLES_ATTR)
        customer = event.get(CUSTOMER_ATTR)
        tenants = event.get(TENANTS_ATTR) or []
        _LOG.debug(f'Sign up event: Customer: {customer}, roles: {roles}, '
                   f'username: {username}')
        if not all([username, password, customer, roles]):
            _LOG.error('You must specify all required parameters: username, '
                       'password, customer, roles.')
            raise build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='You must specify all required parameters: username, '
                        'password, customer, roles.')

        if not isinstance(roles, list):
            roles = [roles]

        non_existing = self.access_control_service.get_non_existing_roles(
            roles=roles)
        if non_existing:
            _LOG.error(f'Invalid role names: {non_existing}')
            raise build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid role names: {", ".join(non_existing)}')
        self.user_service.save(username=username, password=password,
                               customer=customer, roles=roles,
                               tenants=tenants)
        _LOG.debug(f'Saving user: {username}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'The user {username} was created')
