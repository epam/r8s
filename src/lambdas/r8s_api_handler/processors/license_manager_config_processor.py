from commons import (RESPONSE_BAD_REQUEST_CODE, build_response,
                     RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE)
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    HOST_ATTR, PORT_ATTR, \
    PROTOCOL_ATTR, STAGE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.setting import Setting
from services.setting_service import SettingsService

_LOG = get_logger('r8s-lm-config-processor')


class LicenseManagerConfigProcessor(AbstractCommandProcessor):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            DELETE_METHOD: self.delete,
        }

    def get(self, event):
        _LOG.info(f'{GET_METHOD} License Manager access-config event: {event}')

        configuration: dict = self.settings_service. \
            get_license_manager_access_data()
        return build_response(
            code=RESPONSE_OK_CODE,
            content=configuration or []
        )

    def post(self, event: dict):
        _LOG.info(
            f'{POST_METHOD} License Manager access-config event: {event}'
        )
        if self.settings_service.get_license_manager_access_data():
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='License Manager config-data already exists.'
            )
        # TODO check access ?
        setting = self.settings_service. \
            create_license_manager_access_data_configuration(
                host=event[HOST_ATTR],
                port=event.get(PORT_ATTR),
                protocol=event.get(PROTOCOL_ATTR),
                stage=event.get(STAGE_ATTR)
            )

        _LOG.info(f'Persisting License Manager config-data: {setting.value}.')
        self.settings_service.save(setting=setting)
        return build_response(
            code=RESPONSE_OK_CODE, content=setting.value
        )

    def delete(self, event: dict):
        _LOG.info(f'{DELETE_METHOD} License Manager access-config event:'
                  f' {event}')

        configuration: Setting = \
            self.settings_service.get_license_manager_access_data(
                value=False
            )
        if not configuration:
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='License Manager config-data does not exist.'
            )
        _LOG.info(f'Removing License Manager config-data:'
                  f' {configuration.value}.')
        self.settings_service.delete(setting=configuration)
        return build_response(
            code=RESPONSE_OK_CODE,
            content='License Manager config-data has been removed.'
        )
