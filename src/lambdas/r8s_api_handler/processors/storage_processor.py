from commons import (RESPONSE_BAD_REQUEST_CODE, validate_params,
                     build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE,
                     RESPONSE_OK_CODE)
from commons.constants import GET_METHOD, POST_METHOD, PATCH_METHOD, \
    DELETE_METHOD, NAME_ATTR, TYPE_ATTR, ACCESS_ATTR, ID_ATTR, SERVICE_ATTR, \
    BUCKET_NAME_ATTR, PREFIX_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.storage import StorageServiceEnum, StorageTypeEnum, Storage, \
    S3Storage
from services.storage_service import StorageService

_LOG = get_logger('r8s-storage-processor')


class StorageProcessor(AbstractCommandProcessor):
    def __init__(self, storage_service: StorageService):
        self.storage_service = storage_service
        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

    def get(self, event):
        _LOG.debug(f'Get storage event: {event}')

        name = event.get(NAME_ATTR)
        storage_id = event.get(ID_ATTR)

        if name:
            _LOG.debug(f'Describing storage by name \'{name}\'')
            storages = [self.storage_service.get_by_name(name=name)]
        elif storage_id:
            _LOG.debug(f'Describing storage by id \'{storage_id}\'')
            storages = [self.storage_service.get_by_id(object_id=storage_id)]
        else:
            _LOG.debug(f'Describing all storages')
            storages = self.storage_service.list()

        if not storages or storages and \
                all([storage is None for storage in storages]):
            _LOG.debug(f'No storages matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No storages matching given query'
            )

        _LOG.debug(f'Describing storages dto')
        storages_dto = [storage.get_dto() for storage in storages]

        _LOG.debug(f'Response: {storages_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=storages_dto
        )

    def post(self, event):
        _LOG.debug(f'Create storage event: {event}')
        validate_params(event, (NAME_ATTR, TYPE_ATTR, ACCESS_ATTR))

        name = event.get(NAME_ATTR)
        if self.storage_service.get_by_name(name=name):
            _LOG.error(f'Storage with name \'{name}\' already exists.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Storage with name \'{name}\' already exists.'
            )

        service = event.get(SERVICE_ATTR)
        _LOG.debug(f'Validating storage service: \'{service}\'')
        service = self._validate_storage_service(service=service)

        storage_type = event.get(TYPE_ATTR)
        _LOG.debug(f'Validating storage type: \'{storage_type}\'')
        storage_type = self._validate_storage_type(storage_type=storage_type)

        access = event.get(ACCESS_ATTR)
        _LOG.debug(f'Validating storage type access')
        access = self.storage_service.validate_storage_access(
            service=service,
            access=access
        )

        _LOG.debug(f'Creating storage')
        storage_data = {
            NAME_ATTR: name,
            SERVICE_ATTR: service,
            TYPE_ATTR: storage_type,
            ACCESS_ATTR: access
        }
        storage: Storage = self.storage_service.create(
            storage_data=storage_data
        )
        _LOG.debug(f'Saving storage')
        self.storage_service.save(storage=storage)

        _LOG.debug(f'Describing storage dto')
        storage_dto = storage.get_dto()

        _LOG.debug(f'Response: {storage_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=storage_dto
        )

    def patch(self, event):
        _LOG.debug(f'Patch storage event" {event}')

        validate_params(event, (NAME_ATTR,))

        optional_attrs = (TYPE_ATTR, ACCESS_ATTR)

        if not any([event.get(attr) for attr in optional_attrs]):
            _LOG.error(f'At least one of the following attributes must be '
                       f'specified: {optional_attrs}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'At least one of the following attributes must be '
                        f'specified: {optional_attrs}'
            )

        name = event.get(NAME_ATTR)
        storage = self.storage_service.get_by_name(name=name)
        if not storage:
            _LOG.error(f'Storage with name \'{name}\' does not exists.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Storage with name \'{name}\' does not exists.'
            )

        storage_type = event.get(TYPE_ATTR)
        if storage_type:
            _LOG.debug(f'Validating storage type: \'{storage_type}\'')
            storage_type = self._validate_storage_type(
                storage_type=storage_type)
            if storage_type != storage.type:
                _LOG.debug(f'Updating storage \'{name}\' storage type to '
                           f'{storage_type.value}')
                storage.type = storage_type

        access = event.get(ACCESS_ATTR)
        if access:
            access_doc = None
            if access.get(BUCKET_NAME_ATTR):
                access_doc = {
                    BUCKET_NAME_ATTR: access.get(BUCKET_NAME_ATTR),
                    PREFIX_ATTR: access.get(PREFIX_ATTR)
                }
            elif access.get(PREFIX_ATTR):
                access_doc = {
                    BUCKET_NAME_ATTR: storage.access.bucket_name,
                    PREFIX_ATTR: access.get(PREFIX_ATTR)
                }
            if access_doc:
                _LOG.debug(f'Validating storage type access')
                access_doc = self.storage_service.validate_storage_access(
                    service=storage.service,
                    access=access_doc
                )
                _LOG.debug(f'Updating storage \'{name}\' access to '
                           f'\'{access_doc}\'')
                if isinstance(storage, Storage):
                    storage.access = access_doc.to_mongo().to_dict()
                elif isinstance(storage, S3Storage):
                    storage.access = access_doc

        _LOG.debug(f'Saving updated storage')
        self.storage_service.save(storage=storage)

        _LOG.debug('Describing storage dto')
        storage_dto = storage.get_dto()

        _LOG.debug(f'Response: {storage_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=storage_dto
        )

    def delete(self, event):
        _LOG.debug(f'Delete storage event: {event}')
        storage_id = event.get(ID_ATTR)
        name = event.get(NAME_ATTR)

        if not storage_id and not name:
            _LOG.error(f'Either \'{ID_ATTR}\' or \'{NAME_ATTR}\' must be '
                       f'specified')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Either \'{ID_ATTR}\' or \'{NAME_ATTR}\' must be '
                        f'specified'
            )

        if storage_id:
            _LOG.debug(f'Describing storage by id \'{storage_id}\'')
            storage = self.storage_service.get_by_id(object_id=storage_id)
        else:
            _LOG.debug(f'Describing storage by name \'{name}\'')
            storage = self.storage_service.get_by_name(name=name)

        if not storage:
            _LOG.debug(f'No storage found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No storage found matching given query'
            )

        _LOG.debug(f'Deleting storage')
        self.storage_service.delete(storage=storage)

        if storage_id:
            message = f'Storage with id \'{storage_id}\' has been deleted'
        else:
            message = f'Storage with name \'{name}\' has been deleted'
        _LOG.debug(message)
        return build_response(
            code=RESPONSE_OK_CODE,
            content=message
        )

    @staticmethod
    def _validate_storage_service(service: str):
        if not service:
            default_value = StorageServiceEnum.get_default()
            _LOG.debug(f'No service specified, using default '
                       f'\'{default_value.value}\' value')
            return default_value
        service = service.upper()
        if service in StorageServiceEnum.list():
            return getattr(StorageServiceEnum, service)
        _LOG.debug(f'Invalid service specified. Supported algorithms: '
                   f'{StorageServiceEnum.list()}')
        return build_response(
            code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
            content=f'Invalid service specified. Supported algorithms: '
                    f'{StorageServiceEnum.list()}'
        )

    @staticmethod
    def _validate_storage_type(storage_type):
        storage_type = storage_type.upper()
        if storage_type in StorageTypeEnum.list():
            return getattr(StorageTypeEnum, storage_type)
        _LOG.debug(f'Invalid \'type\' specified. Supported types: '
                   f'{StorageTypeEnum.list()}')
        return build_response(
            code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
            content=f'Invalid \'type\' specified. Supported algorithms: '
                    f'{StorageTypeEnum.list()}'
        )
