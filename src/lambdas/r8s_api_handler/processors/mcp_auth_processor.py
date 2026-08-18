from commons import (
    build_response,
    RESPONSE_OK_CODE,
    RESPONSE_RESOURCE_NOT_FOUND_CODE,
)
from commons.constants import (
    DELETE_METHOD,
    GET_METHOD,
    MCP_JWT_KEY_SSM_NAME,
    PATCH_METHOD,
    POST_METHOD,
    SETTING_MCP_JWT_AUTH,
)
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import (
    AbstractCommandProcessor,
)
from services.setting_service import SettingsService
from services.ssm_service import SSMService

_LOG = get_logger('r8s-mcp-auth-processor')

RESPONSE_CONFLICT_CODE = 409


class McpAuthProcessor(AbstractCommandProcessor):
    def __init__(
        self,
        settings_service: SettingsService,
        ssm_service: SSMService,
    ):
        self.settings_service = settings_service
        self.ssm_service = ssm_service
        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

    @classmethod
    def build(cls) -> 'McpAuthProcessor':
        from services import SERVICE_PROVIDER
        return cls(
            settings_service=SERVICE_PROVIDER.settings_service(),
            ssm_service=SERVICE_PROVIDER.ssm_service(),
        )

    @staticmethod
    def _dto(algorithm: str) -> dict:
        return {'algorithm': algorithm, 'configured': True}

    def get(self, event):
        configuration = (
            self.settings_service.get_mcp_jwt_auth_configuration(value=True)
            or {}
        )
        if not configuration:
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='MCP auth configuration is not found',
            )
        return build_response(
            code=RESPONSE_OK_CODE,
            content=self._dto(
                algorithm=configuration.get('algorithm', 'RS256')
            ),
        )

    def post(self, event):
        if self.settings_service.get_mcp_jwt_auth_configuration(value=False):
            return build_response(
                code=RESPONSE_CONFLICT_CODE,
                content='MCP auth configuration already exists.',
            )
        jwt_key = event.get('jwt')
        if not jwt_key:
            return build_response(code=400, content="'jwt' is required")
        algorithm = event.get('algorithm') or 'RS256'

        _LOG.info('Saving MCP JWT public key to SSM')
        self.ssm_service.create_secret_value(
            secret_name=MCP_JWT_KEY_SSM_NAME,
            secret_value=jwt_key,
        )
        self.settings_service.create_mcp_jwt_auth_configuration(
            algorithm=algorithm
        )
        _LOG.info(f'MCP auth configuration created: algorithm={algorithm}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=self._dto(algorithm=algorithm),
        )

    def patch(self, event):
        setting = self.settings_service.get_mcp_jwt_auth_configuration(
            value=False
        )
        if not setting:
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='MCP auth configuration does not exist.',
            )
        configuration = (
            setting.value if isinstance(setting.value, dict) else {}
        )
        algorithm = configuration.get('algorithm') or 'RS256'

        jwt_key = event.get('jwt')
        if jwt_key:
            _LOG.info('Updating MCP JWT key in SSM')
            self.ssm_service.create_secret_value(
                secret_name=MCP_JWT_KEY_SSM_NAME,
                secret_value=jwt_key,
            )

        new_algorithm = event.get('algorithm')
        if new_algorithm:
            algorithm = new_algorithm
            configuration = dict(configuration)
            configuration['algorithm'] = algorithm
            setting.value = configuration
            self.settings_service.save(setting=setting)

        return build_response(
            code=RESPONSE_OK_CODE,
            content=self._dto(algorithm=algorithm),
        )

    def delete(self, event):
        setting = self.settings_service.get_mcp_jwt_auth_configuration(
            value=False
        )
        if not setting:
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='MCP auth configuration does not exist.',
            )
        _LOG.info('Removing MCP auth configuration')
        self.settings_service.delete(setting=setting)
        self.ssm_service.delete_secret(secret_name=MCP_JWT_KEY_SSM_NAME)
        return build_response(
            code=RESPONSE_OK_CODE,
            content='MCP auth configuration has been deleted.',
        )
