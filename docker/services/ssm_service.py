from commons.log_helper import get_logger

from services.clients.ssm import SSMClient

_LOG = get_logger('custodian-ssm-service')


class SSMService:
    def __init__(self, client: SSMClient):
        self.client = client
        self.__secrets = {}

    def get_secret_value(self, secret_name):
        if secret_name in self.__secrets:
            return self.__secrets[secret_name]

        secret = self.client.get_secret_value(secret_name=secret_name)
        if secret:
            self.__secrets[secret_name] = secret
        return secret

    def get_secret_values(self, secret_names: list):
        return self.client.get_secret_values(secret_names=secret_names)

    def create_secret_value(self, secret_name, secret_value):
        self.client.create_secret(secret_name=secret_name,
                                  secret_value=secret_value)

    def delete_secret(self, secret_name: str):
        self.client.delete_parameter(secret_name=secret_name)
