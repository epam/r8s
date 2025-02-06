import itertools
from typing import Optional, Union, List

from commons.constants import CLOUD_AWS, CLOUD_AZURE, CLOUD_GOOGLE, \
    SUSPICIOUS_PRICE_PER_CPU_THRESHOLD
from commons.log_helper import get_logger
from models.shape import Shape
from models.shape_price import ShapePrice, DEFAULT_CUSTOMER
from services.health_checks.abstract_health_check import AbstractHealthCheck
from services.health_checks.check_result import CheckCollectionResult, \
    CheckResult
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService

_LOG = get_logger(__name__)

CHECK_ID_COUNT_CHECK = 'SHAPES_COUNT'
CHECK_ID_REGION_PRICE_CHECK = 'REGION_PRICE_COUNT'
CHECK_ID_MISSING_PRICE_CHECK = 'MISSING_PRICE'
CHECK_ID_SUSPICIOUS_PRICE_CHECK = 'SUSPICIOUS_PRICE'


class ShapeCountCheck(AbstractHealthCheck):

    def identifier(self) -> str:
        return CHECK_ID_COUNT_CHECK

    def remediation(self) -> Optional[str]:
        return f'Upload shapes data for clouds that have no shapes'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans for clouds/regions ' \
               f'with no shapes'

    def check(self, aws_shapes, azure_shapes, gcp_shapes, *args, **kwargs) \
            -> Union[List[CheckResult], CheckResult]:
        count_map = {
            CLOUD_AWS: len(aws_shapes),
            CLOUD_AZURE: len(azure_shapes),
            CLOUD_GOOGLE: len(gcp_shapes),
        }
        if not all([value for value in count_map.values()]):
            return self.not_ok_result(
                details=count_map
            )
        return self.ok_result(details=count_map)


class RegionPriceCheck(AbstractHealthCheck):

    def identifier(self) -> str:
        return CHECK_ID_REGION_PRICE_CHECK

    def remediation(self) -> Optional[str]:
        return f'Upload shape price data for clouds that have no prices'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans for clouds with no prices'

    def check(self, prices: List[ShapePrice], *args, **kwargs) \
            -> Union[List[CheckResult], CheckResult]:
        price_map = self.get_region_map(prices=prices)

        clouds = (CLOUD_AWS, CLOUD_AZURE, CLOUD_GOOGLE)
        if not all([price_map.get('DEFAULT', {}).get(c) for c in clouds]):
            return self.not_ok_result(
                details=price_map
            )
        return self.ok_result(details=price_map)

    @staticmethod
    def get_region_map(prices):
        price_map = {
            DEFAULT_CUSTOMER: {
                CLOUD_AWS: {},
                CLOUD_AZURE: {},
                CLOUD_GOOGLE: {}
            }
        }

        _LOG.debug(f'Counting prices by customer/cloud/region')
        for price in prices:
            customer = price.customer

            if customer not in price_map:
                price_map[customer] = {}

            cloud = price.cloud.value

            if cloud not in price_map[customer]:
                price_map[customer][cloud] = {}

            region = price.region
            if region not in price_map[customer][cloud]:
                price_map[customer][cloud][region] = 0

            price_map[customer][cloud][region] += 1
        return price_map


class MissingPricesCheck(AbstractHealthCheck):

    def identifier(self) -> str:
        return CHECK_ID_MISSING_PRICE_CHECK

    def remediation(self) -> Optional[str]:
        return f'Upload shape price data for shapes with missing linked prices'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to receive savings estimation for ' \
               f'shapes with missing linked prices'

    def check(self, aws_shapes, azure_shapes, gcp_shapes,
              prices: List[ShapePrice], *args, **kwargs) \
            -> Union[List[CheckResult], CheckResult]:
        price_name_mapping = {price.name: price for price in prices}

        shapes_with_missing_prices = []
        _LOG.debug(f'Searching for shapes without prices')
        for shape in itertools.chain(aws_shapes, azure_shapes, gcp_shapes):
            if not price_name_mapping.get(shape.name):
                shapes_with_missing_prices.append(shape.name)

        if shapes_with_missing_prices:
            return self.not_ok_result(
                details={"missing_prices": shapes_with_missing_prices}
            )
        return self.ok_result()


class SuspiciousPriceCheck(AbstractHealthCheck):

    def __init__(self, shape_price_service: ShapePriceService):
        self.shape_price_service = shape_price_service

    def identifier(self) -> str:
        return CHECK_ID_SUSPICIOUS_PRICE_CHECK

    def remediation(self) -> Optional[str]:
        return f'Upload shape price data with realistic prices'

    def impact(self) -> Optional[str]:
        return f'R8s may work incorrectly due to the difference in ' \
               f'shape specs in comparison to price'

    def check(self, aws_shapes: List[Shape], azure_shapes: List[Shape],
              gcp_shapes: List[Shape], prices: List[ShapePrice]) \
            -> Union[List[CheckResult], CheckResult]:
        shapes = list(itertools.chain(aws_shapes, azure_shapes, gcp_shapes))
        shape_name_cpu_mapping = self._shape_cpu_mapping(
            shapes=shapes
        )
        suspicious_prices = []

        for price in prices:
            on_demand_price = price.on_demand
            cpu_count = shape_name_cpu_mapping.get(price.name)
            if not isinstance(cpu_count, (int, float)):
                continue
            if not isinstance(on_demand_price, (int, float)):
                price_dto = self.shape_price_service.get_dto(shape_price=price)
                suspicious_prices.append(price_dto)
                continue
            price_per_cpu = on_demand_price / cpu_count
            if price_per_cpu > SUSPICIOUS_PRICE_PER_CPU_THRESHOLD:
                price_dto = self.shape_price_service.get_dto(shape_price=price)
                suspicious_prices.append(price_dto)

        if suspicious_prices:
            return self.not_ok_result(
                details={'suspicious_prices': suspicious_prices})
        return self.ok_result()

    @staticmethod
    def _shape_cpu_mapping(shapes: list):
        shape_name_mapping = {}
        for shape in shapes:
            shape_name_mapping[shape.name] = shape.cpu
        return shape_name_mapping


class ShapeCheckHandler:
    def __init__(self, shape_service: ShapeService,
                 shape_price_service: ShapePriceService):
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service

        self.checks = [
            ShapeCountCheck(),
            RegionPriceCheck(),
            MissingPricesCheck(),
            SuspiciousPriceCheck(shape_price_service=self.shape_price_service)
        ]

    def check(self):
        _LOG.debug(f'Describing aws shapes')
        aws_shapes = list(self.shape_service.list(cloud=CLOUD_AWS))

        _LOG.debug(f'Describing azure shapes')
        azure_shapes = list(self.shape_service.list(cloud=CLOUD_AZURE))

        _LOG.debug(f'Describing google shapes')
        gcp_shapes = list(self.shape_service.list(cloud=CLOUD_GOOGLE))

        _LOG.debug(f'Got {len(aws_shapes)} AWS, {len(azure_shapes)} azure and '
                   f'{len(gcp_shapes)} GOOGLE shapes.')

        prices = self.shape_price_service.list()

        storage_checks = []
        for check_instance in self.checks:
            check_result = check_instance.check(
                aws_shapes=aws_shapes,
                azure_shapes=azure_shapes,
                gcp_shapes=gcp_shapes,
                prices=prices
            )

            storage_checks.append(check_result)

        shapes_result = CheckCollectionResult(
            id='SHAPES',
            type='SHAPE',
            details=storage_checks
        )

        return [shapes_result.as_dict()]
