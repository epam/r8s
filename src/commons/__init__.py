import uuid
from datetime import datetime

from commons.constants import (PASSWORD_ATTR, ID_TOKEN_ATTR,
                               REFRESH_TOKEN_ATTR, AUTHORIZATION_PARAM)
from commons.exception import ApplicationException

RESPONSE_BAD_REQUEST_CODE = 400
RESPONSE_UNAUTHORIZED = 401
RESPONSE_FORBIDDEN_CODE = 403
RESPONSE_RESOURCE_NOT_FOUND_CODE = 404
RESPONSE_OK_CODE = 200
RESPONSE_INTERNAL_SERVER_ERROR = 500
RESPONSE_NOT_IMPLEMENTED = 501
RESPONSE_SERVICE_UNAVAILABLE_CODE = 503


def build_response(content, code=200):
    if code == RESPONSE_OK_CODE:
        if isinstance(content, str):
            return {
                'code': code,
                'body': {
                    'message': content
                }
            }
        elif isinstance(content, dict):
            return {
                'code': code,
                'body': {
                    'items': [content]
                }
            }
        return {
            'code': code,
            'body': {
                'items': content
            }
        }
    raise ApplicationException(
        code=code,
        content=content
    )


def raise_error_response(code, content):
    raise ApplicationException(code=code, content=content)


def get_iso_timestamp():
    return datetime.now().isoformat()


def get_missing_parameters(event, required_params_list):
    missing_params_list = []
    for param in required_params_list:
        if event.get(param) is None:
            missing_params_list.append(param)
    return missing_params_list


def validate_params(event, required_params_list):
    """
    Checks if all required parameters present in lambda payload.
    :param event: the lambda payload
    :param required_params_list: list of the lambda required parameters
    :return: bad request response if some parameter[s] is/are missing,
        otherwise - none
    """
    missing_params_list = get_missing_parameters(event, required_params_list)

    if missing_params_list:
        raise_error_response(RESPONSE_BAD_REQUEST_CODE,
                             'Bad Request. The following parameters '
                             'are missing: {0}'.format(missing_params_list))


def secure_event(event: dict,
                 secured_keys=(PASSWORD_ATTR, ID_TOKEN_ATTR,
                               REFRESH_TOKEN_ATTR, AUTHORIZATION_PARAM)):
    result_event = {}
    if not isinstance(event, dict):
        return event
    for key, value in event.items():
        if isinstance(value, dict):
            result_event[key] = secure_event(
                event=value,
                secured_keys=secured_keys)
        if isinstance(value, list):
            result_event[key] = []
            for item in value:
                result_event[key].append(secure_event(item))
        elif key in secured_keys:
            result_event[key] = '*****'
        else:
            result_event[key] = secure_event(value)

    return result_event


def generate_id():
    return str(uuid.uuid4())


class RequestContext:
    def __init__(self, request_id: str = None):
        self.aws_request_id: str = request_id or str(uuid.uuid4())


def _import_request_context():
    """Imports request_context global variable from abstract_api_handler_lambda
    and abstract_lambda. Only one of them will be initialized, but here we
    cannot know which will. So just try"""
    from services.abstract_api_handler_lambda import REQUEST_CONTEXT as first
    from services.abstract_lambda import REQUEST_CONTEXT as second
    if not first and not second:
        return RequestContext('Custom trace_id')
    return first if first else second
