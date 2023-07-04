import json

import boto3

from commons.log_helper import get_logger
from services.environment_service import EnvironmentService

_LOG = get_logger(__name__)


class LambdaClient:
    def __init__(self, environment_service: EnvironmentService):
        self.alias = environment_service.lambdas_alias_name()
        self._client = None
        self._environment = environment_service

    @property
    def client(self):
        """Returns client for saas. For on-prem the method is not used"""
        if not self._client:
            self._client = boto3.client(
                'lambda', self._environment.aws_region())
        return self._client

    def invoke_function_async(self, function_name, event=None):
        if self.alias:
            function_name = f'{function_name}:{self.alias}'
        return self.client.invoke(
            FunctionName=function_name,
            InvocationType='Event',
            Payload=json.dumps(event or {}).encode())
