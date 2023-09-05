from abc import abstractmethod

from commons import secure_event
from commons.log_helper import get_logger

_LOG = get_logger('r8s-abstract_processor')


class AbstractCommandProcessor:
    @abstractmethod
    def process(self, event) -> dict:
        pass

    def handle_command(self, event):
        _LOG.debug(f'Event before processing: {secure_event(event)}')
        content = self.process(event=event)
        _LOG.debug(f'Content after processing: {secure_event(content)}')
        return content
