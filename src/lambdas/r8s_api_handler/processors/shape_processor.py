from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_OK_CODE, RESPONSE_RESOURCE_NOT_FOUND_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, GET_METHOD, PATCH_METHOD, \
    DELETE_METHOD, NAME_ATTR, CLOUD_ATTR, CPU_ATTR, MEMORY_ATTR, \
    NETWORK_THROUGHPUT_ATTR, IOPS_ATTR, FAMILY_TYPE_ATTR, \
    PHYSICAL_PROCESSOR_ATTR, ARCHITECTURE_ATTR, SHAPE_ATTRIBUTES
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.base_model import CloudEnum
from services.shape_price_service import ShapePriceService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-shape-processor')


class ShapeProcessor(AbstractCommandProcessor):
    def __init__(self, shape_service: ShapeService,
                 shape_price_service: ShapePriceService):
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service

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
        _LOG.debug(f'Describe shape event: {event}')

        cloud = event.get(CLOUD_ATTR)
        name = event.get(NAME_ATTR)

        shapes = []
        if name:
            _LOG.debug(f'Describing shape by name \'{name}\'')
            shape = self.shape_service.get(name=name)
            if shape:
                shapes.append(shape)
        elif cloud:
            _LOG.debug(f'Describing shapes by cloud \'{cloud.upper()}\'')
            shapes = self.shape_service.list(cloud=cloud)
        else:
            _LOG.debug(f'Describing all shapes')
            shapes = self.shape_service.list()

        if not shapes:
            _LOG.error(f'No shapes found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No shapes found matching given query.'
            )

        _LOG.debug(f'Describing shapes dto')
        response = [self.shape_service.get_dto(shape=shape)
                    for shape in shapes]

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def post(self, event):
        _LOG.debug(f'Create shape event: {event}')
        validate_params(event, (NAME_ATTR, CLOUD_ATTR, CPU_ATTR, MEMORY_ATTR,
                                NETWORK_THROUGHPUT_ATTR, IOPS_ATTR,
                                FAMILY_TYPE_ATTR, PHYSICAL_PROCESSOR_ATTR,
                                ARCHITECTURE_ATTR))

        name = event.get(NAME_ATTR)

        if self.shape_service.get(name):
            _LOG.error(f'Shape with name \'{name}\' already exists.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Shape with name \'{name}\' already exists.'
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

        shape_data = {k: event.get(k) for k in SHAPE_ATTRIBUTES}

        _LOG.debug(f'Validating shape data: {shape_data}')
        self._validate(shape_data=shape_data)

        _LOG.debug(f'Creating shape')
        shape = self.shape_service.create(shape_data=shape_data)

        _LOG.debug(f'Saving shape \'{shape.name}\'')
        self.shape_service.save(shape=shape)

        _LOG.debug(f'Describing shape dto')
        response = self.shape_service.get_dto(shape=shape)

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def patch(self, event):
        _LOG.debug(f'Update shape event: {event}')

        validate_params(event, (NAME_ATTR,))

        shape_name = event.get(NAME_ATTR)
        _LOG.debug(f'Describing shape with name \'{shape_name}\'')
        shape = self.shape_service.get(name=shape_name)

        if not shape:
            _LOG.warning(f'Shape with name \'{shape_name}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Shape with name \'{shape_name}\' does not exist.'
            )
        update_attributes = list(SHAPE_ATTRIBUTES)
        update_attributes.remove(NAME_ATTR)

        update_shape_data = {k: event.get(k) for k in update_attributes
                             if event.get(k) is not None}
        update_shape_data.pop(NAME_ATTR, None)
        if not update_shape_data:
            _LOG.error(f'At least one of the following attributes must be '
                       f'specified: \'{", ".join(update_attributes)}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'At least one of the following attributes must be '
                        f'specified: \'{", ".join(update_attributes)}\''
            )
        _LOG.debug(f'Updating shape items')
        self.shape_service.update(shape=shape, update_data=update_shape_data)

        _LOG.debug(f'Saving shape \'{shape.name}\'')
        self.shape_service.save(shape=shape)

        _LOG.debug(f'Describing shape dto')
        response = self.shape_service.get_dto(shape=shape)

        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def delete(self, event):
        _LOG.debug(f'Remove shape event: {event}')

        validate_params(event, (NAME_ATTR,))

        shape_name = event.get(NAME_ATTR)
        _LOG.debug(f'Describing shape with name \'{shape_name}\'')
        shape = self.shape_service.get(name=shape_name)

        if not shape:
            _LOG.warning(f'Shape with name \'{shape_name}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Shape with name \'{shape_name}\' does not exist.'
            )

        _LOG.debug(f'Searching for prices associated with shape '
                   f'\'{shape_name}\'')
        shape_prices = self.shape_price_service.list(
            name=shape_name
        )
        if shape_prices:
            _LOG.debug(f'Going to delete \'{len(shape_prices)}\' prices '
                       f'associated with shape \'{shape_name}\'')
            for shape_price in shape_prices:
                self.shape_price_service.delete(shape_price=shape_price)

        _LOG.debug(f'Deleting shape \'{shape_name}\'')
        self.shape_service.delete(shape=shape)

        _LOG.debug(f'Shape \'{shape_name}\' has been deleted.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Shape \'{shape_name}\' has been deleted.'
        )

    def _validate(self, shape_data: dict):
        errors = []

        errors.extend(self._validate_number(
            key=CPU_ATTR, value=shape_data.get(CPU_ATTR),
            min_value=1, max_value=512))
        errors.extend(self._validate_number(
            key=MEMORY_ATTR, value=shape_data.get(MEMORY_ATTR),
            min_value=0.5, max_value=1024))
        errors.extend(self._validate_number(
            key=NETWORK_THROUGHPUT_ATTR,
            value=shape_data.get(NETWORK_THROUGHPUT_ATTR),
            min_value=0, max_value=10000))
        errors.extend(self._validate_number(
            key=IOPS_ATTR, value=shape_data.get(IOPS_ATTR),
            min_value=0, max_value=100000))

        if errors:
            _LOG.error(f'Bad request. {", ".join(errors)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Bad request. {", ".join(errors)}'
            )

    @staticmethod
    def _validate_number(key, value, min_value=None, max_value=None):
        errors = []
        if not isinstance(value, (float, int)):
            _LOG.error(f'\'{key}\' attribute must be a valid number.')
            return [f'\'{key}\' attribute must be a valid number.']
        if min_value and value < min_value:
            _LOG.debug(f'\'{key}\' attribute must be greater than '
                       f'{min_value}')
            errors.append(f'\'{key}\' attribute must be greater than '
                          f'{min_value}')
        if max_value and value > max_value:
            _LOG.debug(f'\'{key}\' attribute must be less than '
                       f'{max_value}')
            errors.append(f'\'{key}\' attribute must be less than '
                          f'{max_value}')
        return errors
