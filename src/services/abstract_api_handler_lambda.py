from abc import abstractmethod

from commons import build_response, ApplicationException, \
    RESPONSE_INTERNAL_SERVER_ERROR, RESPONSE_FORBIDDEN_CODE, secure_event
from commons import validate_params
from commons.log_helper import get_logger
from services import SERVICE_PROVIDER
from services.rbac.endpoint_to_permission_mapping import \
    ENDPOINT_PERMISSION_MAPPING

PARAM_USER_ID = 'user_id'
PARAM_REQUEST_PATH = 'request_path'
PARAM_HTTP_METHOD = 'http_method'
PARAM_CUSTOMER = 'customer'
PARAM_USER_CUSTOMER = 'user_customer'
REQUEST_CONTEXT = None

_LOG = get_logger('abstract-api-handler-lambda')


class AbstractApiHandlerLambda:

    @abstractmethod
    def validate_request(self, event) -> dict:
        """
        Validates event attributes
        :param event: lambda incoming event
        :return: dict with attribute_name in key and error_message in value
        """
        pass

    @abstractmethod
    def handle_request(self, event, context):
        """
        Inherited lambda function code
        :param event: lambda event
        :param context: lambda context
        :return:
        """
        pass

    def lambda_handler(self, event, context):
        try:
            _LOG.debug(f'Request: {secure_event(event=event)}')

            _LOG.debug('Checking user permissions')
            validate_params(event=event,
                            required_params_list=[PARAM_REQUEST_PATH,
                                                  PARAM_HTTP_METHOD])
            target_permission = self.__get_target_permission(event=event)
            if not target_permission:  # required to access signup/signin
                _LOG.debug(f'No permissions provided for the given endpoint: '
                           f'{event.get(PARAM_REQUEST_PATH)} and method: '
                           f'{event.get(PARAM_HTTP_METHOD)}')
            else:
                validate_params(event=event,
                                required_params_list=[PARAM_USER_ID])
                if not SERVICE_PROVIDER.access_control_service(). \
                        is_allowed_to_access(
                    event=event, target_permission=target_permission):
                    _LOG.debug(f'User \'{event.get(PARAM_USER_ID)}\' is not '
                               f'allowed to access the resource: '
                               f'{event.get(PARAM_REQUEST_PATH)}')
                    return build_response(
                        code=RESPONSE_FORBIDDEN_CODE,
                        content=f'You are not allowed to access the resource '
                                f'{target_permission}')
            errors = self.validate_request(event=event)
            if errors:
                return build_response(code=400,
                                      content=errors)
            execution_result = self.handle_request(event=event,
                                                   context=context)
            _LOG.debug(f'Response: {execution_result}')
            return execution_result
        except ApplicationException as e:
            _LOG.error(f'Error occurred; Event: {secure_event(event)}; '
                       f'Error: {e}')
            return build_response(code=e.code,
                                  content=e.content)
        except Exception as e:
            _LOG.error(
                f'Unexpected error occurred; Event: {secure_event(event)}; '
                f'Error: {e}')
            return build_response(code=RESPONSE_INTERNAL_SERVER_ERROR,
                                  content='Internal server error')

    def skip_auth(self, event, context):
        errors = self.validate_request(event=event)
        if errors:
            return build_response(code=400,
                                  content=errors)
        try:
            execution_result = self.handle_request(event=event,
                                                   context=context)
            _LOG.debug(f'Response: {execution_result}')
            return execution_result
        except ApplicationException as e:
            _LOG.error(f'Error occurred; Event: {event}; Error: {e}')
            return build_response(code=e.code,
                                  content=e.content)
        except Exception as e:
            _LOG.error(
                f'Unexpected error occurred; Event: {event}; Error: {e}')
            return build_response(code=RESPONSE_INTERNAL_SERVER_ERROR,
                                  content='Internal server error')

    @staticmethod
    def __get_target_permission(event):
        request_path = event.get(PARAM_REQUEST_PATH)
        http_method = event.get(PARAM_HTTP_METHOD)

        path_items = request_path.split('/')
        path_items = [item.strip() for item in path_items if item.strip()]
        del path_items[0]  # remove deploy stage
        request_path = '/' + '/'.join(path_items) + '/'
        target_permission = ENDPOINT_PERMISSION_MAPPING.get(
            request_path, {}).get(http_method, False)
        return target_permission
