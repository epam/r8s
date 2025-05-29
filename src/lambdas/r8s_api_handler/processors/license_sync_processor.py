from commons import RESPONSE_OK_CODE, RESPONSE_RESOURCE_NOT_FOUND_CODE, \
    build_response, validate_params, RESPONSE_BAD_REQUEST_CODE
from commons.constants import APPLICATION_ID_ATTR, \
    MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE
from commons.constants import POST_METHOD
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.algorithm_service import AlgorithmService
from services.license_manager_service import LicenseManagerService
from services.rightsizer_application_service import \
    RightSizerApplicationService

_LOG = get_logger('r8s-license-sync-processor')


class LicenseSyncProcessor(AbstractCommandProcessor):
    def __init__(self, license_manager_service: LicenseManagerService,
                 algorithm_service: AlgorithmService,
                 application_service: RightSizerApplicationService):

        self.license_manager_service = license_manager_service
        self.algorithm_service = algorithm_service
        self.application_service = application_service

        self.method_to_handler = {
            POST_METHOD: self.post,
        }

    def post(self, event):
        _LOG.debug(f'Sync license event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR,))
        application_id = event.get(APPLICATION_ID_ATTR)

        application = self.application_service.get_application_by_id(
            application_id=application_id
        )
        if (not application or application.type !=
                MAESTRO_RIGHTSIZER_LICENSES_APPLICATION_TYPE):
            _LOG.error('No RIGHTSIZER_LICENSES application matching '
                       'given query found.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No RIGHTSIZER_LICENSES application matching '
                        'given query found.'
            )
        app_meta = self.application_service.get_application_meta(
            application=application
        )
        license_key = app_meta.license_key
        if not license_key:
            _LOG.error(f'Invalid application {application_id} meta '
                       f'configuration. Missing "license_key" parameter')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid application {application_id} meta '
                        f'configuration. Missing "license_key" parameter'
            )

        self._execute_license_sync(
            application=application,
        )

        _LOG.debug(
            f'License {license_key} from application {application_id} has been synced')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'License {license_key} from application {application_id} has been synced'
        )

    def _execute_license_sync(self, application):
        app_meta = self.application_service.get_application_meta(
            application=application
        )
        license_key = app_meta.license_key
        _LOG.info(f'Syncing license {license_key} '
                  f'in application {application.application_id}')
        response = self.license_manager_service.synchronize_license(
            license_key=license_key,
            customer=application.customer_id
        )
        if not response.status_code == 200:
            return

        license_data = response.json()['items'][0]

        _LOG.debug(f'Updating license {license_key}')
        application = self.application_service.update_license(
            application=application,
            license_data=license_data
        )
        _LOG.debug(f'Updating licensed algorithm')

        self.algorithm_service.sync_licensed_algorithm(
            license_data=license_data,
            customer=application.customer_id
        )
        return application
