from typing import Optional, Union, List

from commons.constants import CHECK_TYPE_STORAGE
from commons.log_helper import get_logger
from models.storage import Storage, StorageTypeEnum
from services.clients.s3 import S3Client
from services.health_checks.abstract_health_check import AbstractHealthCheck
from services.health_checks.check_result import CheckCollectionResult, \
    CheckResult
from services.storage_service import StorageService

_LOG = get_logger(__name__)

CHECK_ID_STORAGE_BUCKET = 'STORAGE_BUCKET'
CHECK_ID_METRIC_FILES = 'METRIC_FILES'

METRIC_FILES_TO_CHECK = 5000


class MetricFilesCheck(AbstractHealthCheck):

    def __init__(self, storage_service: StorageService,
                 s3_client: S3Client):
        self.storage_service = storage_service
        self.s3_client = s3_client

    def identifier(self) -> str:
        return CHECK_ID_METRIC_FILES

    def remediation(self) -> Optional[str]:
        return f'Upload metric files with valid folder structure to storage'

    def impact(self) -> Optional[str]:
        return f'No instances will be processed with this storage'

    def check(self, storage: Storage) -> Union[List[CheckResult], CheckResult]:
        storage_json = storage.get_json()
        bucket_name = storage_json.get('access', {}).get('bucket_name')

        if not bucket_name:
            return self.not_ok_result(
                {'error': "\'bucket_name\' does not specified"}
            )

        if not self.s3_client.is_bucket_exists(bucket_name=bucket_name):
            return self.not_ok_result(
                {'error': f'S3 Bucket \'{bucket_name}\' does not exist'}
            )

        storage_type = storage_json.get('type')

        if storage_type == StorageTypeEnum.STORAGE.value:
            return self.ok_result()

        metric_files_check = self._metric_files_check(storage=storage)
        if not metric_files_check['instances']:
            return self.not_ok_result(
                details=metric_files_check
            )
        return self.ok_result(details=metric_files_check)

    def _metric_files_check(self, storage: Storage):
        storage_json = storage.get_json()
        bucket_name = storage_json.get('access', {}).get('bucket_name')

        prefix = storage_json.get('access', {}).get('prefix')

        files = self.s3_client.list_objects_gen(
            bucket_name=bucket_name,
            prefix=prefix,
            only_keys=True)

        sets = [set() for _ in range(7)]
        error_files = []

        for index, file_ in enumerate(files):
            if index >= METRIC_FILES_TO_CHECK:
                break
            if not file_.endswith('.csv'):
                continue
            if prefix:
                file_ = file_[len(prefix) + 1:]
            path_parts = file_.split('/')
            if len(path_parts) != 7:
                error_files.append(file_)
                continue
            for part_index, item in enumerate(path_parts):
                sets[part_index].add(item)

        sets = [self._limit(list(s)) for s in sets]
        error_files = self._limit(error_files)
        storage_result = {
            'resource_types': sets[0],
            'customers': sets[1], 'clouds': sets[2],
            'tenants': sets[3], 'regions': sets[4],
            'dates': sets[5], 'instances': sets[6],
            'folder_structure_errors': error_files}
        return storage_result

    @staticmethod
    def _limit(items: list, limit=10):
        if len(items) > limit:
            l = len(items) - limit
            items = items[0:limit]
            items.append(f'{l} more items.')
        return items



class StorageBucketCheck(AbstractHealthCheck):

    def __init__(self, storage_service: StorageService,
                 s3_client: S3Client):
        self.storage_service = storage_service
        self.s3_client = s3_client

    def identifier(self) -> str:
        return CHECK_ID_STORAGE_BUCKET

    def remediation(self) -> Optional[str]:
        return f'Update storage with valid S3 bucket name'

    def impact(self) -> Optional[str]:
        return f'You won\'t be able to submit scans with this storage'

    def check(self, storage: Storage) -> Union[List[CheckResult], CheckResult]:
        storage_json = storage.get_json()
        bucket_name = storage_json.get('access', {}).get('bucket_name')

        if not bucket_name:
            return self.not_ok_result(
                {'error': "\'bucket_name\' does not specified"}
            )

        if not self.s3_client.is_bucket_exists(bucket_name=bucket_name):
            return self.not_ok_result(
                {'error': f'S3 Bucket \'{bucket_name}\' does not exist'}
            )

        return self.ok_result()


class StorageCheckHandler:
    def __init__(self, storage_service: StorageService, s3_client: S3Client):
        self.storage_service = storage_service
        self.s3_client = s3_client

        self.checks = [
            StorageBucketCheck(storage_service=self.storage_service,
                               s3_client=self.s3_client),
            MetricFilesCheck(storage_service=self.storage_service,
                             s3_client=self.s3_client)
        ]

    def check(self):
        _LOG.debug(f'Listing storages')
        storages = self.storage_service.list()
        if not storages:
            _LOG.warning(f'No active storages found')
            result = CheckCollectionResult(
                id='NONE',
                type=CHECK_TYPE_STORAGE,
                details=[]
            )
            return result.as_dict()

        result = []

        for storage in storages:
            storage_checks = []
            for check_instance in self.checks:
                check_result = check_instance.check(storage=storage)

                storage_checks.append(check_result)

            storage_result = CheckCollectionResult(
                id=storage.name,
                type=CHECK_TYPE_STORAGE,
                details=storage_checks
            )

            result.append(storage_result.as_dict())
        return result
