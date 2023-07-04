import boto3

from commons.log_helper import get_logger

_LOG = get_logger('api-gateway-client')

RIGHTSIZER_API_NAME = 'r8s-api'

URL_TEMPLATE = "{api_id}.execute-api.{region}.amazonaws.com"


class ApiGatewayClient:
    def __init__(self, region):
        self.client = boto3.client('apigateway', region)
        self.region = region

    def get_r8s_api_host(self):
        response = self.client.get_rest_apis(limit=100)
        if not response:
            return
        items = response.get('items', [])

        for api_item in items:
            if api_item.get('name') != RIGHTSIZER_API_NAME:
                continue
            api_url = URL_TEMPLATE.format(api_id=api_item.get('id'),
                                          region=self.region)
            return api_url
