from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_OK_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, USERNAME_ATTR, PASSWORD_ATTR, \
    REFRESH_TOKEN_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.user_service import CognitoUserService
from commons.__version__ import __version__

_LOG = get_logger('r8s-refresh-processor')


class RefreshProcessor(AbstractCommandProcessor):
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
                      f'refresh processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def post(self, event):
        refresh_token = event.get(REFRESH_TOKEN_ATTR)
        _LOG.debug(f'Refresh token event')

        response = self.user_service.refresh_token(refresh_token)
        if not response:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid refresh token provided')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )
