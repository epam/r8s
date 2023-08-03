from base64 import standard_b64decode

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    KID_ATTR, ALG_ATTR, VALUE_ATTR, KEY_ID_ATTR, ALGORITHM_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.clients.abstract_key_management import IKey
from services.key_management_service import KeyManagementService, FORMAT_ATTR, \
    PUBLIC_KEY_ATTR
from services.license_manager_service import LicenseManagerService
from services.setting_service import SettingsService

_LOG = get_logger('r8s-lm-config-processor')

PEM_ATTR = 'PEM'
UNSUPPORTED_ALG_TEMPLATE = 'Algorithm:\'{alg}\' is not supported.'
KEY_OF_ENTITY_TEMPLATE = '{key}:\'{kid}\' of \'{uid}\' {entity}'

UNRESOLVABLE_ERROR = 'Request has run into an issue, which could not' \
                     ' be resolved.'


class LicenseManagerClientProcessor(AbstractCommandProcessor):
    def __init__(self, settings_service: SettingsService,
                 key_management_service: KeyManagementService,
                 license_manager_service: LicenseManagerService):
        self.settings_service = settings_service
        self.key_management_service = key_management_service
        self.license_manager_service = license_manager_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            DELETE_METHOD: self.delete,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'job definition processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event: dict):
        _LOG.info(f'{GET_METHOD} License Manager Client-Key event: {event}')

        fmt = event.get(FORMAT_ATTR) or PEM_ATTR

        configuration: dict = self.settings_service. \
                                  get_license_manager_client_key_data() or {}

        kid = configuration.get(KID_ATTR)
        alg = configuration.get(ALG_ATTR)

        response = None

        if kid and alg:
            prk_kid = self.license_manager_service.derive_client_private_key_id(
                kid=kid
            )
            _LOG.info(f'Going to retrieve private-key by \'{prk_kid}\'.')
            prk = self.key_management_service.get_key(kid=prk_kid, alg=alg)
            if not prk:
                message = KEY_OF_ENTITY_TEMPLATE.format(
                    key='PrivateKey', kid=prk_kid, uid=alg,
                    entity='algorithm'
                )
                _LOG.warning(message + ' could not be retrieved.')
            else:
                _LOG.info(f'Going to derive a public-key of \'{kid}\'.')
                puk: IKey = self._derive_puk(prk=prk.key)
                if puk:
                    managed = self.key_management_service. \
                        instantiate_managed_key(
                        kid=kid, key=puk, alg=alg
                    )
                    _LOG.info(f'Going to export the \'{kid}\' public-key.')
                    response = self._response_dto(
                        exported_key=managed.export_key(frmt=fmt),
                        value_attr=PUBLIC_KEY_ATTR
                    )
        if not response:
            _LOG.warning(f'No valid License Manager Client-Key found.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No valid License Manager Client-Key found.'
            )
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event: dict):
        _LOG.info(
            f'{POST_METHOD} License Manager Client-Key event: {event}'
        )

        self.check_properly_encoded_key(event)
        kid = event.get(KEY_ID_ATTR)
        alg = event.get(ALGORITHM_ATTR)
        raw_prk = event.get('private_key')
        frmt = event.get(FORMAT_ATTR)

        # Decoding is taking care of within the validation layer.

        if self.settings_service. \
                get_license_manager_client_key_data(value=False):
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='License Manager Client-Key already exists.'
            )

        prk = self.key_management_service.import_key(
            alg=alg, key_value=raw_prk
        )

        puk = self._derive_puk(prk=prk)
        if not puk:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Improper private-key.'
            )

        if not prk:
            return build_response(
                content=UNSUPPORTED_ALG_TEMPLATE.format(alg=alg),
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE
            )

        prk = self.key_management_service.instantiate_managed_key(
            alg=alg, key=prk,
            kid=self.license_manager_service.derive_client_private_key_id(
                kid=kid
            )
        )

        message = KEY_OF_ENTITY_TEMPLATE.format(
            key='PublicKey', kid=prk.kid, uid=prk.alg, entity='algorithm'
        )

        _LOG.info(message + ' has been instantiated.')

        self.key_management_service.save_key(
            kid=prk.kid, key=prk.key, frmt=frmt
        )

        managed_puk = self.key_management_service.instantiate_managed_key(
            kid=kid, alg=alg, key=puk
        )

        setting = self.settings_service.create_license_manager_client_key_data(
            kid=kid, alg=alg
        )

        _LOG.info(f'Persisting License Manager Client-Key data:'
                  f' {setting.value}.')

        self.settings_service.save(setting=setting)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=self._response_dto(
                exported_key=managed_puk.export_key(frmt=frmt),
                value_attr=PUBLIC_KEY_ATTR
            )
        )

    def delete(self, event: dict):
        _LOG.info(f'{DELETE_METHOD} License Manager Client-Key event: {event}')

        requested_kid = event.get(KEY_ID_ATTR)

        head = 'License Manager Client-Key'
        unretained = ' does not exist'
        code = RESPONSE_RESOURCE_NOT_FOUND_CODE
        # Default 404 error-response.
        content = head + unretained

        setting = self.settings_service. \
            get_license_manager_client_key_data(value=False)

        if not setting:
            return build_response(
                code=code,
                content=head + unretained
            )

        configuration = setting.value
        kid = configuration.get(KID_ATTR)
        alg = configuration.get(ALG_ATTR)

        if not (kid and alg):
            _LOG.warning(head + ' does not contain \'kid\' or \'alg\' data.')
            return build_response(code=code, content=content)

        if kid != requested_kid:
            _LOG.warning(
                head + f' does not contain {requested_kid} \'kid\' data.')
            return build_response(code=code, content=content)

        is_key_data_removed = False

        prk_kid = self.license_manager_service.derive_client_private_key_id(
            kid=kid
        )

        _LOG.info(f'Going to retrieve private-key by \'{prk_kid}\'.')
        prk = self.key_management_service.get_key(kid=prk_kid, alg=alg)

        prk_head = KEY_OF_ENTITY_TEMPLATE.format(
            key='PrivateKey', kid=prk_kid, uid=alg, entity='algorithm'
        )
        if not prk:
            _LOG.warning(prk_head + ' could not be retrieved.')
        else:
            if not self.key_management_service.delete_key(kid=prk.kid):
                _LOG.warning(prk_head + ' could not be removed.')
            else:
                is_key_data_removed = True

        if self.settings_service.delete(setting=setting):
            committed = 'completely ' if is_key_data_removed else ''
            committed += 'removed'
            code = RESPONSE_OK_CODE
            content = head + f' has been {committed}'

        return build_response(code=code, content=content)

    @staticmethod
    def _response_dto(exported_key: dict, value_attr: str):
        if VALUE_ATTR in exported_key:
            exported_key[value_attr] = exported_key.pop(VALUE_ATTR)
        return exported_key

    @staticmethod
    def _derive_puk(prk: IKey):
        try:
            puk = prk.public_key()
        except (Exception, ValueError) as e:
            message = 'Public-Key could not be derived out of a ' \
                      f'private one, due to: "{e}".'
            _LOG.warning(message)
            puk = None
        return puk

    @staticmethod
    def check_properly_encoded_key(values):
        is_encoded = values.get('b64_encoded')
        key: str = values.get('private_key')
        if is_encoded:
            try:
                key = standard_b64decode(key).decode()
            except (TypeError, BaseException):
                raise ValueError(
                    '\'private_key\' must be a safe to decode'
                    ' base64-string.'
                )
            values['private_key'] = key
        return values
