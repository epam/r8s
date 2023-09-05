from r8s_service.adapter_client import AdapterClient
from r8s_service.config import ConfigurationProvider
from r8s_service.logger import get_logger

SYSTEM_LOG = get_logger('r8s.service.initializer')


def init_configuration():
    config = ConfigurationProvider()
    adapter_sdk = AdapterClient(adapter_api=config.api_link,
                                token=config.access_token)
    return adapter_sdk
