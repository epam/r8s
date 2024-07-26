from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    RESPONSE_OK_CODE, RESPONSE_RESOURCE_NOT_FOUND_CODE, build_response
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import LICENSE_KEY_ATTR
from commons.constants import POST_METHOD
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.license import License
from services.algorithm_service import AlgorithmService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService

_LOG = get_logger('r8s-license-sync-processor')


class LicenseSyncProcessor(AbstractCommandProcessor):
    def __init__(self, license_service: LicenseService,
                 license_manager_service: LicenseManagerService,
                 algorithm_service: AlgorithmService):
        self.license_service = license_service
        self.license_manager_service = license_manager_service
        self.algorithm_service = algorithm_service

        self.method_to_handler = {
            POST_METHOD: self.post,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'license processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def post(self, event):
        _LOG.debug(f'Sync license event: {event}')
        license_key = event.get(LICENSE_KEY_ATTR)

        licenses = list(self.license_service.list_licenses(
            license_key=license_key))

        license_key_list = [l.license_key for l in licenses]
        _LOG.debug(f'Licenses to sync: '
                   f'{", ".join(license_key_list)}')
        if not license_key_list:
            _LOG.error('No licenses matching given query found.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No licenses matching given query found.'
            )
        for license_ in licenses:
            _LOG.debug(f'Syncing license \'{license_.license_key}\'')
            self._execute_license_sync(
                license_obj=license_,
            )
        _LOG.debug(f'Licenses: {", ".join(license_key_list)} '
                   f'have been synced')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Licenses: {", ".join(license_key_list)} '
                    f'have been synced'
        )

    def _execute_license_sync(self, license_obj: License):
        _LOG.info(f'Syncing license \'{license_obj.license_key}\'')
        customer = list(license_obj.customers.keys())[0]
        response = self.license_manager_service.synchronize_license(
            license_key=license_obj.license_key,
            customer=customer
        )
        if not response.status_code == 200:
            return

        license_data = response.json()['items'][0]

        _LOG.debug(f'Updating license {license_obj.license_key}')
        license_obj = self.license_service.update_license(
            license_obj=license_obj,
            license_data=license_data
        )
        _LOG.debug(f'Updating licensed algorithm')
        for customer in license_obj.customers.keys():
            self.algorithm_service.sync_licensed_algorithm(
                license_data=license_data,
                customer=customer
            )
        return license_obj
