import json
from typing import Callable
from importlib import import_module
from threading import Thread

import boto3

from commons import RequestContext, ApplicationException
from commons.log_helper import get_logger
from services.environment_service import EnvironmentService

_LOG = get_logger(__name__)

REPORT_GENERATOR_LAMBDA_NAME = 'r8s-report-generator'

LAMBDA_TO_PACKAGE_MAPPING = {
    REPORT_GENERATOR_LAMBDA_NAME: 'r8s_report_generator',
}


class LambdaClient:
    def __init__(self, environment_service: EnvironmentService):
        self.alias = environment_service.lambdas_alias_name()
        self.is_docker = environment_service.is_docker()
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
        if self.is_docker:
            return self._invoke_function_docker(
                function_name=function_name,
                event=event
            )
        else:
            if self.alias:
                function_name = f'{function_name}:{self.alias}'
            return self.client.invoke(
                FunctionName=function_name,
                InvocationType='Event',
                Payload=json.dumps(event or {}).encode())

    @staticmethod
    def _derive_handler(function_name):
        """
        Produces a lambda handler function class,
        adhering to the LAMBDA_TO_PACKAGE_MAPPING.
        :return:Union[AbstractLambda, Type[None]]
        """
        _LOG.debug(f'Importing lambda \'{function_name}\'')
        package_name = LAMBDA_TO_PACKAGE_MAPPING.get(function_name)
        if not package_name:
            return
        return getattr(
            import_module(f'lambdas.{package_name}.handler'), 'HANDLER'
        )

    def _invoke_function_docker(self, function_name, event=None, wait=False):
        handler = self._derive_handler(function_name)
        if handler:
            _LOG.debug(f'Handler: {handler}')
            args = [{}, RequestContext()]
            if event:
                args[0] = event
            if wait:
                response = self._handle_execution(
                    handler.lambda_handler, *args
                )
            else:
                Thread(target=self._handle_execution, args=(
                    handler.lambda_handler, *args)).start()
                response = dict(StatusCode=202)
            return response

    @staticmethod
    def _handle_execution(handler: Callable, *args):
        try:
            _response = handler(*args)
        except ApplicationException as e:
            _response = dict(code=e.code, body=dict(message=e.content))
        return _response
