from typing import Dict, Callable

from commons import secure_event, RESPONSE_BAD_REQUEST_CODE, \
    raise_error_response
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.log_helper import get_logger

_LOG = get_logger('r8s-abstract_processor')


class AbstractCommandProcessor:
    method_to_handler: Dict[str, Callable]

    def process(self, event: dict) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'{self.__class__.__name__}'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def handle_command(self, event):
        _LOG.debug(f'Event before processing: {secure_event(event)}')
        content = self.process(event=event)
        _LOG.debug(f'Content after processing: {secure_event(content)}')
        return content
