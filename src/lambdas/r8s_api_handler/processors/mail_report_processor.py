from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    validate_params, RESPONSE_FORBIDDEN_CODE, RESPONSE_OK_CODE, build_response
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, CUSTOMER_ATTR, TENANTS_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.clients.lambda_func import LambdaClient

_LOG = get_logger('r8s-mail-report-processor')

REPORT_GENERATOR_LAMBDA_NAME = 'r8s-report-generator'


class MailReportProcessor(AbstractCommandProcessor):
    def __init__(self, lambda_client: LambdaClient):
        self.lambda_client = lambda_client
        self.method_to_handler = {
            POST_METHOD: self.post,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'role processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def post(self, event):
        validate_params(event, (CUSTOMER_ATTR, TENANTS_ATTR))

        customer = event.get(CUSTOMER_ATTR)
        tenants = event.get(TENANTS_ATTR)

        user_customer = event.get(PARAM_USER_CUSTOMER)
        if user_customer != customer and user_customer != 'admin':
            _LOG.error(f'User is not allowed to access customer '
                       f'\'{customer}\' resource.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'User is not allowed to access customer '
                        f'\'{customer}\' resource'
            )
        _LOG.debug(f'Invoking report generation for customer \'{customer}\' '
                   f'tenants: {tenants}')
        response = self.lambda_client.invoke_function_async(
            function_name=REPORT_GENERATOR_LAMBDA_NAME,
            event={CUSTOMER_ATTR: customer, TENANTS_ATTR: tenants}
        )
        if response.get('StatusCode') == 202:
            _LOG.debug(f'Lambda \'{REPORT_GENERATOR_LAMBDA_NAME}\' '
                       f'has been invoked.')
            return build_response(
                code=RESPONSE_OK_CODE,
                content=f'Report generation has been initiated for customer '
                        f'\'{customer}\' tenants: {", ".join(tenants)}'
            )
