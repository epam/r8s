import os

import click
import requests

from modular_cli_sdk.services.credentials_manager import CredentialsProvider
from r8scli.service.local_response_processor import LocalCommandResponse
from r8scli.service.logger import get_logger, get_user_logger

SYSTEM_LOG = get_logger('r8s.service.config')
USER_LOG = get_user_logger('user')

MODULE_NAME = 'r8s'


def create_configuration(api_link, context):
    message = None
    try:
        requests.get(api_link)
        # to allow connect to localhost
        # if response.status_code == 404:
        #     return f'Invalid API link: {api_link}. Status code: 404.'
    except (requests.exceptions.MissingSchema,
            requests.exceptions.ConnectionError):
        message = f'Invalid API link: {api_link}'
    except requests.exceptions.InvalidURL:
        message =  f'Invalid URL \'{api_link}\': No host specified.'
    except requests.exceptions.InvalidSchema:
        message =  f'Invalid URL \'{api_link}\': No network protocol specified ' \
               f'(http/https).'

    if message:
        return LocalCommandResponse(body={'message': message})

    configuration = CredentialsProvider(module_name=MODULE_NAME,
                                        context=context)
    config_data = dict(api_link=api_link)
    configuration.credentials_manager.store(config=config_data)

    response = {'message': 'Great! The r8s tool api_link has been configured.'}
    return LocalCommandResponse(body=response)


def save_token(access_token: str = None, refresh_token: str = None):
    context = click.get_current_context()
    configuration = CredentialsProvider(module_name=MODULE_NAME,
                                        context=context)
    config = configuration.credentials_manager.extract()
    if not config:
        SYSTEM_LOG.exception(f'r8s tool is not configured. Please contact'
                             f'the support team.')
        return 'r8s tool is not configured. Please contact the support team.'

    config[CONF_ACCESS_TOKEN] = access_token
    if refresh_token:
        config[CONF_REFRESH_TOKEN] = refresh_token
    configuration.credentials_manager.store(config=config)
    response = {'message': 'Great! The r8s tool access token has been saved.'}
    return LocalCommandResponse(body=response)


def clean_up_configuration():
    context = click.get_current_context()
    configuration = CredentialsProvider(
        module_name=MODULE_NAME, context=context)
    result = configuration.credentials_manager.clean_up()
    response = {'message': result}
    del configuration
    return LocalCommandResponse(body=response)


CONF_ACCESS_TOKEN = 'access_token'
CONF_REFRESH_TOKEN = 'refresh_token'
CONF_API_LINK = 'api_link'

REQUIRED_PROPS = [CONF_API_LINK]


class ConfigurationProvider:

    def __init__(self):
        context = click.get_current_context()
        configuration = CredentialsProvider(module_name=MODULE_NAME,
                                            context=context)
        self.config_dict = configuration.credentials_manager.extract()
        if not self.config_dict:
            raise AssertionError(
                'The r8s tool is not configured. Please execute the '
                'following command: \'r8s configure\'.')
        missing_property = []
        for prop in REQUIRED_PROPS:
            if not self.config_dict.get(prop):
                missing_property.append(prop)
        if missing_property:
            raise AssertionError(
                f'r8s configuration is broken. '
                f'The following properties are '
                f'required but missing: {missing_property}')

        SYSTEM_LOG.info(
            f'r8s configuration has been loaded')

    @property
    def api_link(self):
        return self.config_dict.get(CONF_API_LINK)

    @property
    def access_token(self):
        return self.config_dict.get(CONF_ACCESS_TOKEN)

    @property
    def refresh_token(self):
        return self.config_dict.get(CONF_REFRESH_TOKEN)