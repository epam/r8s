from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_OK_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, USERNAME_ATTR, PASSWORD_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.user_service import CognitoUserService
from commons.__version__ import __version__

_LOG = get_logger('r8s-signin-processor')


class SignInProcessor(AbstractCommandProcessor):
    def __init__(self, user_service: CognitoUserService):
        self.user_service = user_service
        self.method_to_handler = {
            POST_METHOD: self.post,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'signin processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def post(self, event):
        username = event.get(USERNAME_ATTR)
        _LOG.debug(f'Sign in event for user: {username}')
        password = event.get(PASSWORD_ATTR)
        if not username or not password:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='You must specify both username and password')

        _LOG.debug(f'Going to initiate the authentication flow')
        auth_result = self.user_service.initiate_auth(
            username=username,
            password=password)
        if not auth_result:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Incorrect username or password')

        _state = "contains" if auth_result.get(
            "ChallengeName") else "does not contain"
        _LOG.debug(f'Authentication initiation response '
                   f'{_state} the challenge')

        if auth_result.get('ChallengeName'):
            _LOG.debug(f'Responding to an authentication challenge '
                       f'{auth_result.get("ChallengeName")} ')
            auth_result = self.user_service.respond_to_auth_challenge(
                challenge_name=auth_result['ChallengeName'])
        refresh_token = auth_result['AuthenticationResult']['RefreshToken']
        id_token = auth_result['AuthenticationResult']['IdToken']

        response = {'id_token': id_token, 'api_version': __version__}
        if refresh_token:
            response['refresh_token'] = refresh_token

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )
