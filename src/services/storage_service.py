from bson import ObjectId
from bson.errors import InvalidId
from mongoengine.errors import DoesNotExist, ValidationError

from commons import build_response, RESPONSE_INTERNAL_SERVER_ERROR, \
    RESPONSE_BAD_REQUEST_CODE, RESPONSE_RESOURCE_NOT_FOUND_CODE
from commons.constants import BUCKET_NAME_ATTR, PREFIX_ATTR, SERVICE_ATTR, \
    JSON_LINES_EXTENSION
from commons.log_helper import get_logger
from models.storage import Storage, StorageServiceEnum, S3Storage, S3Access
from services.clients.s3 import S3Client

_LOG = get_logger('r8s-storage-service')

NO_RESULTS_ERROR = 'No job results available'


class StorageService:
    def __init__(self, s3_client: S3Client):
        self.s3_client = s3_client

        self.storage_service_class_mapping = {
            StorageServiceEnum.S3_BUCKET: S3Storage
        }

    @staticmethod
    def list():
        return list(Storage.objects.all())

    def get(self, identifier: str):
        _LOG.debug(f'Describing storage by identifier: \'{identifier}\'')
        try:
            _LOG.debug('Trying to convert to bson id')
            ObjectId(identifier)
            _LOG.debug('Describing storage by id')
            return self.get_by_id(object_id=identifier)
        except InvalidId:
            _LOG.debug('Describing storage by name')
            return self.get_by_name(name=identifier)

    @staticmethod
    def get_by_id(object_id):
        try:
            return Storage.objects.get(id=object_id)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def get_by_name(name: str):
        try:
            return Storage.objects.get(name=name)
        except (DoesNotExist, ValidationError):
            return None

    def create(self, storage_data: dict):
        storage_service = storage_data.get(SERVICE_ATTR)
        storage_class = self.storage_service_class_mapping.get(storage_service)
        storage = storage_class(**storage_data)
        return storage

    @staticmethod
    def save(storage: Storage):
        storage.save()

    @staticmethod
    def delete(storage: Storage):
        storage.delete()

    def validate_storage_access(self, service, access):
        access_validator_mapping = {
            StorageServiceEnum.S3_BUCKET: self._validate_s3_access
        }
        validator = access_validator_mapping.get(service)
        if not validator:
            _LOG.error(f'Unknown storage service: {service}')
            return build_response(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content='Internal Server Error.'
            )
        return validator(access)

    def _validate_s3_access(self, access: dict):
        allowed_fields = (BUCKET_NAME_ATTR, PREFIX_ATTR)
        bucket_name = access.get(BUCKET_NAME_ATTR)

        if not bucket_name:
            _LOG.error(f'Missing required attribute \'{BUCKET_NAME_ATTR}\' '
                       f'for s3 access.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Missing required attribute \'{BUCKET_NAME_ATTR}\' '
                        f'for s3 storage.'
            )
        if not self.s3_client.is_bucket_exists(bucket_name=bucket_name):
            _LOG.error(f'Specified s3 bucket \'{bucket_name}\' does '
                       f'not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Specified s3 bucket \'{bucket_name}\' does '
                        f'not exist.'
            )
        access = {k: v for k, v in access.items() if k in allowed_fields}
        return S3Access(**access)

    def download_job_results(self, storage: Storage, job_id: str,
                             *args, **kwargs):
        type_downloader_mapping = {
            S3Storage: self._download_job_results_s3
        }
        downloader = type_downloader_mapping.get(storage.__class__)

        if not downloader:
            return build_response(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content='Internal Server Error'
            )
        return downloader(storage, job_id, *args, **kwargs)

    def _download_job_results_s3(self, storage: S3Storage, job_id,
                                 customer=None, cloud=None, tenant=None,
                                 region=None):
        access = storage.access
        if access.prefix:
            prefix = '/'.join((access.prefix, job_id))
        else:
            prefix = job_id
        bucket_name = access.bucket_name

        _LOG.debug(f'Listing objects in bucket \'{bucket_name}\'. '
                   f'Prefix: \'{prefix}\'')

        objects = self.s3_client.list_objects(bucket_name=bucket_name,
                                              prefix=prefix)

        if not objects:
            _LOG.error(NO_RESULTS_ERROR)
            return build_response(
                content=RESPONSE_BAD_REQUEST_CODE,
                code=NO_RESULTS_ERROR
            )

        object_keys = [obj.get('Key') for obj in objects if
                       obj.get('Key').endswith(JSON_LINES_EXTENSION)]

        object_keys = self.filter_result_files(
            s3_keys=object_keys,
            prefix=prefix,
            customer=customer,
            cloud=cloud,
            tenant=tenant,
            region=region
        )
        items = []
        for key in object_keys:
            _LOG.debug(f'Processing file \'{key}\'')

            content = self.s3_client.get_json_lines_file_content(
                bucket_name=bucket_name,
                full_file_name=key
            )

            customer_, cloud_, tenant_, region_ = self._parse_folders(
                s3_key=key, prefix=prefix
            )

            for item in content:
                item['customer'] = customer_
                item['cloud'] = cloud_
                item['tenant'] = tenant_
                item['region'] = region_
                items.append(item)
        return items

    def list_object_with_presigned_urls(self, storage: Storage, job_id):
        access = storage.access
        if access.prefix:
            prefix = '/'.join((access.prefix, job_id))
        else:
            prefix = job_id
        bucket_name = access.bucket_name

        _LOG.debug(f'Listing objects in bucket \'{bucket_name}\'. '
                   f'Prefix: \'{prefix}\'')

        objects = self.s3_client.list_objects(bucket_name=bucket_name,
                                              prefix=prefix)

        if not objects:
            _LOG.error(NO_RESULTS_ERROR)
            return build_response(
                content=RESPONSE_BAD_REQUEST_CODE,
                code=NO_RESULTS_ERROR
            )

        objects = [obj for obj in objects if
                   obj.get('Key').endswith(JSON_LINES_EXTENSION)]

        for file in objects:
            url = self.s3_client.generate_presigned_url(
                bucket_name=bucket_name,
                full_file_name=file.get('Key'),
                expires_in_sec=3600
            )
            file['presigned_url'] = url
        return objects

    def list_metric_files(self, data_source: Storage, customer,
                          cloud=None, tenant=None, regions=None,
                          timestamp=None):
        access = data_source.access

        _LOG.debug(f'Listing objects in bucket \'{access.bucket_name}\'. '
                   f'Prefix: \'{access.prefix}\'')
        prefixes = []

        if regions:
            for region in regions:
                result = self._build_prefix(
                    prefix=access.prefix,
                    customer=customer,
                    tenant=tenant,
                    cloud=cloud,
                    region=region,
                    timestamp=timestamp
                )
                prefixes.append(result)
        else:
            result = self._build_prefix(
                prefix=access.prefix,
                customer=customer,
                tenant=tenant,
                cloud=cloud
            )
            prefixes.append(result)

        objects = []
        for prefix in prefixes:
            prefix_objects = self.s3_client.list_objects(
                bucket_name=access.bucket_name,
                prefix=prefix,
                limit=5000
            )
            if prefix_objects:
                objects.extend(prefix_objects)
        return [item for item in objects if item.get('Key').endswith('.csv')]

    def filter_result_files(self, s3_keys, prefix, customer=None,
                            cloud=None, tenant=None, region=None):
        filtered = []
        for key in s3_keys:
            expected = (customer, cloud, tenant, region)
            actual = self._parse_folders(s3_key=key, prefix=prefix)

            for expected_value, actual_value in zip(expected, actual):
                if expected_value and expected_value != actual_value:
                    break
            else:
                filtered.append(key)
        return filtered

    @staticmethod
    def _parse_folders(s3_key, prefix):
        """
        Extracts customer, cloud, tenant and region from result file path
        """
        path = s3_key.replace(prefix, '', 1).strip('/')

        folders = path.split('/')
        customer = folders[0]
        cloud = folders[1]
        tenant = folders[2]
        region = folders[3].replace('.jsonl', '')

        return customer, cloud, tenant, region

    @staticmethod
    def _build_prefix(customer, prefix=None, cloud=None, tenant=None,
                      region=None, timestamp=None):
        prefix_parts = [customer, cloud, tenant, region, timestamp]

        index = None
        for index, part in enumerate(prefix_parts):
            if not part:
                break

        prefix_parts = prefix_parts[0:index]
        if prefix:
            prefix_parts.insert(0, prefix)
        return '/'.join(prefix_parts)
