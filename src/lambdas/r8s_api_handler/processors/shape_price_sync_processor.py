import json
from typing import Optional

from commons import (RESPONSE_BAD_REQUEST_CODE, build_response,
                     validate_params, RESPONSE_OK_CODE)
from commons.constants import POST_METHOD, REGION_ATTR, OS_ATTR, CLOUD_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.shape import CloudEnum
from models.shape_price import ShapePrice
from services.clients.pricing import PricingClient
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService

_LOG = get_logger('r8s-shape-price-sync-processor')

ALLOWED_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                   'ca-central-1', 'eu-west-1', 'eu-central-1', 'eu-west-2',
                   'eu-west-3', 'eu-north-1', 'ap-northeast-1',
                   'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
                   'ap-south-1', 'sa-east-1']
OS_LINUX = 'Linux'
OS_WINDOWS = 'Windows'
ALLOWED_OS = [OS_LINUX, OS_WINDOWS]
DEFAULT_CUSTOMER = 'DEFAULT'


class ShapePriceSyncProcessor(AbstractCommandProcessor):
    def __init__(self,
                 shape_price_service: ShapePriceService,
                 pricing_client: PricingClient,
                 settings_service: SettingsService):
        self.shape_price_service = shape_price_service
        self.pricing_client = pricing_client
        self.settings_service = settings_service

        self.method_to_handler = {
            POST_METHOD: self.post
        }

    def post(self, event):
        _LOG.debug(f'Update shape price event: {event}')
        validate_params(event, (REGION_ATTR, CLOUD_ATTR))

        cloud = event.get(CLOUD_ATTR, CloudEnum.CLOUD_AWS.value)
        if cloud != CloudEnum.CLOUD_AWS.value:
            _LOG.error(f'Invalid cloud specified \'{cloud}\'. '
                       f'Only {CloudEnum.CLOUD_AWS.value} is supported.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid cloud specified \'{cloud}\'. '
                        f'Only {CloudEnum.CLOUD_AWS.value} is supported.'
            )

        region = event.get(REGION_ATTR)
        operating_system = event.get(OS_ATTR)

        if operating_system and operating_system.title() not in ALLOWED_OS:
            _LOG.error(f'Invalid operating system '
                       f'specified \'{operating_system}\'. ')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid operating system '
                        f'specified \'{operating_system}\'. '
                        f'Allowed operating systems: {", ".join(ALLOWED_OS)}'
            )
        if not operating_system:
            operating_system = OS_LINUX

        if region not in ALLOWED_REGIONS:
            _LOG.error(f'Invalid region specified \'{region}\'. ')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid region specified \'{region}\'. '
                        f'Allowed region: {", ".join(ALLOWED_REGIONS)}'
            )
        _LOG.debug(f'Listing shape prices for region: {region}, '
                   f'operating system: {operating_system}')
        entries = self.pricing_client.list_region_os_prices(
            operating_system=operating_system.title(),
            region=region
        )
        _LOG.debug(f'Processing obtained entries: {len(entries)}')
        shape_prices = []
        for entry in entries:
            shape_price = self._process_entry(entry)
            if not shape_price:
                continue
            shape_prices.append(shape_price)

        _LOG.debug(f'Updating shape prices: {len(shape_prices)}')
        for shape_price in shape_prices:
            _LOG.debug(
                f'Saving shape price: {shape_price.name}, '
                f'{shape_price.region}, {shape_price.os}')
            self.shape_price_service.save_force(shape_price)

        _LOG.debug(f'Updating setting')
        self.settings_service.update_shape_update_date(
            cloud=CloudEnum.CLOUD_AWS.value
        )

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Shape prices updated successfully for region: {region}, '
                    f'operating system: {operating_system}. '
                    f'Records updated: {len(shape_prices)}'
        )

    def _process_entry(self, entry: str) -> Optional[ShapePrice]:
        _LOG.debug(f'Processing entry: {entry}')
        obj = self._decode_json(entry)
        if not obj:
            return

        attributes = self._extract_attributes(obj)
        if not attributes:
            return

        price_per_unit = self._extract_price(obj)
        if price_per_unit is None or price_per_unit == 0:
            return

        shape_price_data = {
            'customer': DEFAULT_CUSTOMER,
            'cloud': CloudEnum.CLOUD_AWS.value,
            'name': attributes['instance_type'],
            'region': attributes['instance_region'],
            'os': attributes['instance_os'].upper(),
            'on_demand': price_per_unit
        }
        return self.shape_price_service.create(
            shape_price_data=shape_price_data)

    @staticmethod
    def _decode_json(entry: str) -> Optional[dict]:
        try:
            return json.loads(entry)
        except json.JSONDecodeError as e:
            _LOG.error(f'Failed to decode JSON entry: {e}')
            return None

    @staticmethod
    def _extract_attributes(obj: dict) -> Optional[dict]:
        attributes = obj.get("product", {}).get('attributes', {})
        if not attributes:
            _LOG.error('No attributes found in the entry data.')
            return None

        return {
            'instance_type': attributes.get('instanceType'),
            'instance_region': attributes.get('regionCode'),
            'instance_os': attributes.get('operatingSystem')
        }

    @staticmethod
    def _extract_price(obj: dict) -> Optional[float]:
        on_demand = obj.get('terms', {}).get('OnDemand')
        if not on_demand:
            _LOG.warning('No OnDemand terms found in the entry data.')
            return None

        first_key = list(on_demand)[0]
        price_dimensions = on_demand[first_key]['priceDimensions']
        first_key = list(price_dimensions)[0]
        price_per_unit = price_dimensions[first_key]['pricePerUnit']['USD']
        return float(price_per_unit)
