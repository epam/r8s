from commons import RESPONSE_BAD_REQUEST_CODE, build_response, RESPONSE_OK_CODE
from commons.constants import POST_METHOD, REFRESH_TOKEN_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.user_service import CognitoUserService

_LOG = get_logger('r8s-refresh-processor')


class RefreshProcessor(AbstractCommandProcessor):
    def __init__(self, user_service: CognitoUserService):
        self.user_service = user_service
        self.method_to_handler = {
            POST_METHOD: self.post,
        }

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
