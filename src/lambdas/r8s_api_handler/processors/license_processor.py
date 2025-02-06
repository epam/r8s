from commons import (RESPONSE_BAD_REQUEST_CODE, build_response,
                     RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE,
                     validate_params)
from commons.constants import GET_METHOD, DELETE_METHOD
from commons.constants import LICENSE_KEY_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.license import License
from services.algorithm_service import AlgorithmService
from services.license_service import LicenseService

_LOG = get_logger('r8s-license-processor')


class LicenseProcessor(AbstractCommandProcessor):
    def __init__(self, license_service: LicenseService,
                 algorithm_service: AlgorithmService):

        self.license_service = license_service
        self.algorithm_service = algorithm_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            DELETE_METHOD: self.delete,
        }

    def get(self, event):
        _LOG.debug(f'Describe license event: {event}')
        license_key = event.get(LICENSE_KEY_ATTR)

        _LOG.debug(f'Describing license(s) with key \'{license_key}\'')
        licenses = self.license_service.list_licenses(license_key=license_key)

        if not licenses:
            _LOG.error(f'No licensed found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No licensed found matching given query'
            )

        _LOG.debug(f'Describing license dto')
        response = [self.license_service.get_dto(license_)
                    for license_ in licenses]
        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def delete(self, event):
        _LOG.debug(f'Delete license event: {event}')
        validate_params(event, (LICENSE_KEY_ATTR,))

        license_key = event.get(LICENSE_KEY_ATTR)
        license_: License = self.license_service.get_license(
            license_id=license_key)

        if not license_:
            _LOG.error(f'License with key \'{license_key}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'License with key \'{license_key}\' does not exist.'
            )

        algorithm_name = license_.algorithm_id

        _LOG.debug(f'Describing licensed algorithm \'{algorithm_name}\'')
        algorithm = self.algorithm_service.get_by_name(name=algorithm_name)

        if algorithm:
            _LOG.error(f'Algorithm \'{algorithm_name}\' linked to '
                       f'license \'{license_key}\' must be deleted')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm_name}\' linked to '
                        f'license \'{license_key}\' must be deleted'
            )

        _LOG.debug(f'Deleting license \'{license_key}\'')
        self.license_service.delete(license_obj=license_)

        _LOG.debug(f'License \'{license_key}\' has been deleted')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'License \'{license_key}\' has been deleted'
        )
