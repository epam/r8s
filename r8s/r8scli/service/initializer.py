from r8scli.service.adapter_client import AdapterClient
from r8scli.service.config import ConfigurationProvider
from r8scli.service.logger import get_logger

SYSTEM_LOG = get_logger('r8s.service.initializer')


def init_configuration():
    config = ConfigurationProvider()
    adapter_sdk = AdapterClient(adapter_api=config.api_link,
                                token=config.access_token,
                                refresh_token=config.refresh_token)
    return adapter_sdk
