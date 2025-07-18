import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Union

import boto3
from botocore.client import ClientError
from modular_sdk.services.ssm_service import SecretValue

from commons.constants import ENV_SERVICE_MODE, DOCKER_SERVICE_MODE, \
    ENV_VAULT_TOKEN, ENV_VAULT_HOST, ENV_VAULT_PORT
from commons.log_helper import get_logger
from services.environment_service import EnvironmentService

_LOG = get_logger('ssmclient')


class AbstractSSMClient(ABC):
    def __init__(self, environment_service: EnvironmentService):
        self._environment_service = environment_service

    @abstractmethod
    def get_parameter(self, name: str):
        pass

    @abstractmethod
    def put_parameter(self, secret_name: str, secret_value: SecretValue,
                      secret_type='SecureString') -> bool:
        pass

    @abstractmethod
    def delete_parameter(self, name: str) -> bool:
        pass

    @abstractmethod
    def enable_secrets_engine(self, mount_point=None):
        pass

    @abstractmethod
    def is_secrets_engine_enabled(self, mount_point=None) -> bool:
        pass


class SSMClient(AbstractSSMClient):
    def __init__(self, environment_service: EnvironmentService):
        super().__init__(environment_service)
        self._client = None

    @property
    def client(self):
        if not self._client:
            self._client = boto3.client(
                'ssm', self._environment_service.aws_region())
        return self._client

    def get_parameter(self, name):
        try:
            response = self.client.get_parameter(
                Name=name,
                WithDecryption=True
            )
            value_str = response['Parameter']['Value']
            try:
                return json.loads(value_str)
            except json.decoder.JSONDecodeError:
                return value_str
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(f'Can\'t get secret for name \'{name}\', '
                       f'error code: \'{error_code}\'')

    def put_parameter(self, name: str,
                      value: Union[str, list, dict],
                      secret_type='SecureString'):
        try:
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            self.client.put_parameter(
                Name=name,
                Value=value,
                Overwrite=True,
                Type=secret_type)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(f'Can\'t get secret for name \'{name}\', '
                       f'error code: \'{error_code}\'')

    def delete_parameter(self, name: str):
        try:
            self.client.delete_parameter(Name=name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(f'Can\'t delete secret name \'{name}\', '
                       f'error code: \'{error_code}\'')

    def enable_secrets_engine(self, mount_point=None):
        pass

    def is_secrets_engine_enabled(self, mount_point=None) -> bool:
        pass


class VaultSSMClient(AbstractSSMClient):
    mount_point = 'kv'
    key = 'data'

    def __init__(self, environment_service: EnvironmentService):
        super().__init__(environment_service)
        self._client = None  # hvac.Client

    def _init_client(self):
        assert os.getenv(ENV_SERVICE_MODE) == DOCKER_SERVICE_MODE, \
            "You can init vault handler only if SERVICE_MODE=docker"
        import hvac
        vault_token = os.getenv(ENV_VAULT_TOKEN)
        vault_host = os.getenv(ENV_VAULT_HOST)
        vault_port = os.getenv(ENV_VAULT_PORT)
        _LOG.info('Initializing hvac client')
        self._client = hvac.Client(
            url=f'http://{vault_host}:{vault_port}',
            token=vault_token
        )
        _LOG.info('Hvac client was initialized')

    @property
    def client(self):
        if not self._client:
            self._init_client()
        return self._client

    def get_parameter(self, name: str) -> Optional[SecretValue]:
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=name, mount_point=self.mount_point) or {}
        except Exception as e:  # hvac.InvalidPath
            _LOG.warning(f'Failed to read secret {name} from '
                         f'mount point {self.mount_point}: {e}')
            return
        return response.get('data', {}).get('data', {}).get(self.key)

    def put_parameter(self, name: str, value: SecretValue,
                      secret_type='SecureString') -> bool:
        return self.client.secrets.kv.v2.create_or_update_secret(
            path=name,
            secret={self.key: value},
            mount_point=self.mount_point
        )

    def delete_parameter(self, name: str) -> bool:
        return bool(self.client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=name, mount_point=self.mount_point))

    def enable_secrets_engine(self, mount_point=None):
        try:
            self.client.sys.enable_secrets_engine(
                backend_type='kv',
                path=(mount_point or self.mount_point),
                options={'version': 2}
            )
            return True
        except Exception:  # hvac.exceptions.InvalidRequest
            return False  # already exists

    def is_secrets_engine_enabled(self, mount_point=None) -> bool:
        mount_points = self.client.sys.list_mounted_secrets_engines()
        target_point = mount_point or self.mount_point
        return f'{target_point}/' in mount_points
