import importlib
import json
from functools import cached_property
from typing import Tuple, Optional

from bottle import Bottle, request, Route, HTTPResponse

from commons import ApplicationException, RequestContext, RESPONSE_UNAUTHORIZED
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import COGNITO_USERNAME
from commons.log_helper import get_logger
from connections.auth_extension.cognito_to_jwt_adapter import \
    UNAUTHORIZED_MESSAGE
from exported_module.api.deployment_resources_parser import \
    DeploymentResourcesParser
from services import SERVICE_PROVIDER

_LOG = get_logger(__name__)

RESPONSE_HEADERS = {'Content-Type': 'application/json'}


class DynamicAPI:
    def __init__(self, dr_parser: DeploymentResourcesParser):
        self.app = Bottle(__name__)

        self.dr_parser = dr_parser
        self.api_config = self.dr_parser.generate_api_config()
        self.lambda_module_mapping = self.import_api_lambdas()
        self.generate_api()

    def generate_api(self):
        for request_path, endpoint_meta in self.api_config.items():
            endpoint_methods = endpoint_meta.get('allowed_methods')
            for http_method in endpoint_methods:
                route = Route(app=self.app, rule=request_path,
                              method=http_method,
                              callback=self.api)
                self.app.add_route(route=route)

    @cached_property
    def paths_without_jwt(self) -> set:
        return {
            '/r8s/signin',
            '/r8s/refresh'
        }

    @staticmethod
    def get_token_from_header(header: str) -> Optional[str]:
        if not header or not isinstance(header, str):
            return
        parts = header.split()
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            return parts[1]

    def authorize(self) -> dict:
        """
        May raise ApplicationException.
        Returns a decoded token
        :return: dict
        """
        header = (request.headers.get('Authorization') or
                  request.headers.get('authorization'))
        token = self.get_token_from_header(header)
        if not token:
            raise ApplicationException(
                code=RESPONSE_UNAUTHORIZED,
                content=UNAUTHORIZED_MESSAGE
            )
        return SERVICE_PROVIDER.cognito().decode_token(token)

    def api(self, **path_kwargs):
        try:
            if str(request.path).rstrip('/') in self.paths_without_jwt:
                token_decoded = {}
            else:
                token_decoded = self.authorize()
        except ApplicationException as e:
            return HTTPResponse(
                body=dict(message=e.content),
                status=e.code,
            )

        config_path = str(request.path)
        stage, resource_path = self._split_stage_and_resource(path=config_path)
        if request.url_args:
            # Builds up a proxy-based path.
            for key, value in request.url_args.items():
                # TODO, bug: what if value (which is a value of url args)
                #  is equal, for instance, to api stage???, or to some
                #  part of it. Think about it
                if value in config_path:
                    # Bottle-Routing compatible config path.
                    start = config_path.index(value)
                    prefix = config_path[:start]
                    suffix = config_path[start + len(value):]
                    config_path = prefix + f'<{key}>' + suffix

                    # ApiGateway-2-Lambda compatible request path.
                    start = resource_path.index(value)
                    prefix = resource_path[:start]
                    suffix = resource_path[start + len(value):]
                    resource_path = prefix + '{' + key + '}' + suffix

        endpoint_meta = self.api_config.get(config_path)
        # API-GATEWAY lambda proxy integration event
        event = {
            PARAM_HTTP_METHOD: request.method,
            'headers': dict(request.headers),
            "request_path": '/' + stage.strip('/') + '/' + resource_path.strip(
                '/'),
            "user_id": token_decoded.get(COGNITO_USERNAME),

            'pathParameters': path_kwargs,
            'user_customer': token_decoded.get('cognito:customer'),
            'action': endpoint_meta.get('action')
        }
        if request.method == 'GET':
            event['query'] = dict(querystring=dict(request.query))
            event['body'] = None
        else:
            event['body'] = json.loads(request.body.read().decode())

        lambda_module = self.lambda_module_mapping.get(
            endpoint_meta.get('lambda_name'))
        try:
            response = lambda_module.lambda_handler(event=event,
                                                    context=RequestContext())
            return HTTPResponse(
                body=response.get('body'),
                status=response.get('statusCode'),
                headers=response.get('headers')
            )
        except ApplicationException as e:
            return HTTPResponse(
                body={'message': e.content},
                status=e.code
            )

    @staticmethod
    def import_api_lambdas():
        # TODO add Notification handler lambda?
        # TODO, merge report-generator and report-generator-handler
        _import = importlib.import_module
        return {
            'r8s-api-handler':
                _import('lambdas.r8s_api_handler.handler'),
            'r8s-report-generator':
                _import('lambdas.r8s_report_generator.handler')
        }

    @staticmethod
    def _split_stage_and_resource(path: str) -> Tuple[str, str]:
        """/r8s/account/region -> ("/r8s", "/account/region")"""
        path = path.rstrip('/')
        path = path.lstrip('/')
        first_slash = path.index('/')
        return f'/{path[:first_slash]}', path[first_slash:]
