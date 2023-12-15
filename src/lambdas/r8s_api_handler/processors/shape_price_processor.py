from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, GET_METHOD, PATCH_METHOD, \
    DELETE_METHOD, NAME_ATTR, CLOUD_ATTR, CUSTOMER_ATTR, REGION_ATTR, OS_ATTR, \
    ON_DEMAND_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.base_model import CloudEnum
from models.shape_price import OSEnum, DEFAULT_CUSTOMER
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-shape-price-processor')


class ShapePriceProcessor(AbstractCommandProcessor):
    def __init__(self, shape_service: ShapeService,
                 shape_price_service: ShapePriceService,
                 customer_service: CustomerService):
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service
        self.customer_service = customer_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'shape rule processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe shape price: {event}')

        customer = event.get(PARAM_USER_CUSTOMER)
        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)

        cloud = event.get(CLOUD_ATTR)
        name = event.get(NAME_ATTR)
        region = event.get(REGION_ATTR)
        os = event.get(OS_ATTR)

        customers = [customer]
        if DEFAULT_CUSTOMER not in customers:
            customers.append(DEFAULT_CUSTOMER)

        query_data = {
            CUSTOMER_ATTR: customers,
            NAME_ATTR: name,
            CLOUD_ATTR: cloud,
            REGION_ATTR: region,
            OS_ATTR: os
        }
        _LOG.debug(f'Describing shape pricing from query: {query_data}')
        shape_prices = self.shape_price_service.list(**query_data)

        if not shape_prices:
            _LOG.error('No shape prices found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No shape prices found matching given query.'
            )
        _LOG.debug(f'Describing dto for {len(shape_prices)} shape prices.')
        response = [self.shape_price_service.get_dto(shape_price)
                    for shape_price in shape_prices]
        _LOG.debug(f'Response: {response}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event):
        _LOG.debug(f'Create shape price event: {event}')
        validate_params(event, (NAME_ATTR, CLOUD_ATTR, REGION_ATTR, OS_ATTR,
                                ON_DEMAND_ATTR))

        customer = event.get(PARAM_USER_CUSTOMER)

        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)
            if not customer:
                _LOG.error(f'\'{CUSTOMER_ATTR}\' must be specified for '
                           f'admin users.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'\'{CUSTOMER_ATTR}\' must be specified for '
                            f'admin users.'
                )
            if customer != DEFAULT_CUSTOMER and not \
                    self.customer_service.get(name=customer):
                _LOG.error(f'Customer \'{customer}\' does not exist.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Customer \'{customer}\' does not exist.'
                )
        elif event.get(CUSTOMER_ATTR) and event.get(CUSTOMER_ATTR) != customer:
            _LOG.error(f'You\'re not allowed to create prices for '
                       f'customer \'{event.get(CUSTOMER_ATTR)}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You\'re not allowed to create prices for '
                        f'customer \'{event.get(CUSTOMER_ATTR)}\''
            )

        cloud = event.get(CLOUD_ATTR)
        if cloud not in CloudEnum.list():
            _LOG.warning(f'Unsupported cloud specified \'{cloud}\'. '
                         f'Available clouds: {", ".join(CloudEnum.list())}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Unsupported cloud specified \'{cloud}\'. '
                        f'Available clouds: {", ".join(CloudEnum.list())}'
            )

        os = event.get(OS_ATTR)
        if os not in OSEnum.list():
            _LOG.warning(f'Unsupported os specified \'{cloud}\'. '
                         f'Available options: {", ".join(OSEnum.list())}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Unsupported cloud specified \'{cloud}\'. '
                        f'Available options: {", ".join(OSEnum.list())}'
            )
        on_demand = event.get(ON_DEMAND_ATTR)

        if not isinstance(on_demand, (int, float)) or on_demand <= 0:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{ON_DEMAND_ATTR}\' attribute must be a valid '
                        f'non-negative number.'
            )

        shape_price_exists = self.shape_price_service.get(
            customer=customer, region=event.get(REGION_ATTR),
            os=os, name=event.get(NAME_ATTR),
            use_default_if_missing=False)
        if shape_price_exists:
            _LOG.error('Shape price for the given query already exists.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='Shape price for the given query already exists.'
            )

        shape_price_data = {
            CUSTOMER_ATTR: customer,
            NAME_ATTR: event.get(NAME_ATTR),
            CLOUD_ATTR: cloud,
            REGION_ATTR: event.get(REGION_ATTR),
            OS_ATTR: os,
            ON_DEMAND_ATTR: on_demand
        }
        _LOG.debug(f'Creating shape price from data \'{shape_price_data}\'')

        shape_price = self.shape_price_service.create(
            shape_price_data=shape_price_data)

        _LOG.debug('Saving shape price item')
        self.shape_price_service.save(shape_price=shape_price)

        _LOG.debug('Describing shape price dto')
        response = self.shape_price_service.get_dto(shape_price)

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def patch(self, event):
        _LOG.debug(f'Update shape price event: {event}')
        validate_params(event, (NAME_ATTR, REGION_ATTR, OS_ATTR,
                                ON_DEMAND_ATTR))
        customer = event.get(PARAM_USER_CUSTOMER)

        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)
            if not customer:
                _LOG.error(f'\'{CUSTOMER_ATTR}\' must be specified for '
                           f'admin users.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'\'{CUSTOMER_ATTR}\' must be specified for '
                            f'admin users.'
                )
        elif event.get(CUSTOMER_ATTR) and event.get(CUSTOMER_ATTR) != customer:
            _LOG.error(f'You\'re not allowed to update prices for '
                       f'customer \'{event.get(CUSTOMER_ATTR)}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You\'re not allowed to update prices for '
                        f'customer \'{event.get(CUSTOMER_ATTR)}\''
            )

        shape_price = self.shape_price_service.get(
            customer=customer,
            region=event.get(REGION_ATTR),
            os=event.get(OS_ATTR),
            name=event.get(NAME_ATTR),
            use_default_if_missing=False
        )
        if not shape_price:
            _LOG.error('No shape price found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No shape price found matching given query.'
            )

        on_demand = event.get(ON_DEMAND_ATTR)
        if not isinstance(on_demand, (int, float)) or on_demand <= 0:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{ON_DEMAND_ATTR}\' attribute must be a valid '
                        f'non-negative number.'
            )
        _LOG.debug(f'Setting shape price to \'{on_demand}\'')
        shape_price.on_demand = on_demand

        _LOG.debug('Saving updated shape price item')
        self.shape_price_service.save(shape_price=shape_price)

        _LOG.debug('Describing shape price dto')
        response = self.shape_price_service.get_dto(shape_price)

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def delete(self, event):
        _LOG.debug(f'Remove shape price event: {event}')
        validate_params(event, (NAME_ATTR, CLOUD_ATTR,
                                REGION_ATTR, OS_ATTR))
        customer = event.get(PARAM_USER_CUSTOMER)

        if customer == 'admin':
            customer = event.get(CUSTOMER_ATTR)
            if not customer:
                _LOG.error(f'\'{CUSTOMER_ATTR}\' must be specified for '
                           f'admin users.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'\'{CUSTOMER_ATTR}\' must be specified for '
                            f'admin users.'
                )
        elif event.get(CUSTOMER_ATTR) and event.get(CUSTOMER_ATTR) != customer:
            _LOG.error(f'You\'re not allowed to delete prices for '
                       f'customer \'{event.get(CUSTOMER_ATTR)}\'')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'You\'re not allowed to delete prices for '
                        f'customer \'{event.get(CUSTOMER_ATTR)}\''
            )
        query = {
            CUSTOMER_ATTR: customer,
            NAME_ATTR: event.get(NAME_ATTR),
            REGION_ATTR: event.get(REGION_ATTR),
            OS_ATTR: event.get(OS_ATTR)
        }
        _LOG.debug(f'Describing shape price for query: {query}')
        shape_price = self.shape_price_service.get(
            **query, use_default_if_missing=False)

        if not shape_price:
            _LOG.error('Shape price with the given query does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='Shape price with the given query does not exist.'
            )

        _LOG.debug('Deleting shape price')
        self.shape_price_service.delete(shape_price=shape_price)

        _LOG.debug(f'Shape price for query \'{query}\' has been deleted.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Shape \'{shape_price.name}\' price for '
                    f'\'{shape_price.customer}\' customer, '
                    f'\'{shape_price.region}\' region, '
                    f'\'{shape_price.os.value}\' os has been removed'
        )
