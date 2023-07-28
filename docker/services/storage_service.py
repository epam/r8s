import os
from datetime import datetime, timedelta, date
from glob import glob

from bson import ObjectId
from bson.errors import InvalidId
from mongoengine.errors import DoesNotExist, ValidationError

from commons.constants import SERVICE_ATTR, \
    JOB_STEP_DOWNLOAD_METRICS, CSV_EXTENSION, META_FILE_NAME, ALL
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from models.storage import Storage, StorageServiceEnum, S3Storage
from services.clients.s3 import S3Client

_LOG = get_logger('r8s-storage-service')

DATE_FORMAT = '%Y-%m-%d'


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
            _LOG.debug(f'Trying to convert to bson id')
            ObjectId(identifier)
            _LOG.debug(f'Describing storage by id')
            return self.get_by_id(object_id=identifier)
        except InvalidId:
            _LOG.debug(f'Describing storage by name')
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

    def download_metrics(self, data_source: Storage, output_path: str,
                         scan_customer, scan_clouds, scan_tenants,
                         scan_from_date, scan_to_date):
        type_downloader_mapping = {
            S3Storage: self._download_metrics_s3
        }
        downloader = type_downloader_mapping.get(data_source.__class__)

        if not downloader:
            raise ExecutorException(
                step_name=JOB_STEP_DOWNLOAD_METRICS,
                reason=f'No downloader available for storage class '
                       f'\'{data_source.__class__}\''
            )
        return downloader(data_source, output_path, scan_customer,
                          scan_clouds, scan_tenants, scan_from_date,
                          scan_to_date)

    def _download_metrics_s3(self, data_source: S3Storage, output_path,
                             scan_customer, scan_clouds, scan_tenants,
                             scan_from_date=None, scan_to_date=None):
        access = data_source.access
        prefix = access.prefix
        bucket_name = access.bucket_name

        paths = self._build_s3_paths(prefix=prefix,
                                     scan_customer=scan_customer,
                                     scan_clouds=scan_clouds,
                                     scan_tenants=scan_tenants)

        _LOG.debug(f'Listing objects in bucket \'{bucket_name}\'. '
                   f'from paths: \'{paths}\'')
        objects = []
        if paths:
            for path in paths:
                files = self.s3_client.list_objects(bucket_name=bucket_name,
                                                    prefix=path)
                if files:
                    objects.extend(files)
        else:
            files = self.s3_client.list_objects(bucket_name=bucket_name)
            objects.extend(files)
        objects = [obj for obj in objects if
                   obj.get('Key').endswith(CSV_EXTENSION)
                   or obj.get('Key').endswith(f'/{META_FILE_NAME}')]

        filter_only_dates = self.get_scan_dates_list(
            scan_from_date=scan_from_date,
            scan_to_date=scan_to_date
        )
        if filter_only_dates:
            objects = [obj for obj in objects if obj['Key'].split('/')[-2]
                       in filter_only_dates]
        _LOG.debug(f'{len(objects)} metric/meta files found, downloading')
        for file in objects:
            path = file.get('Key').split('/')
            if len(path) > 0 and path[0] == prefix:
                path = path[1:]
            path = '/'.join(path[:-1])
            output_folder_path = '/'.join((output_path, path))
            os.makedirs(output_folder_path, exist_ok=True)
            self.s3_client.download_file(
                bucket_name=bucket_name,
                full_file_name=file.get('Key'),
                output_folder_path=output_folder_path
            )

    def upload_job_results(self, job_id, storage: Storage,
                           results_folder_path):
        type_uploader_mapping = {
            S3Storage: self._upload_job_results_s3
        }
        downloader = type_uploader_mapping.get(storage.__class__)

        if not downloader:
            raise ExecutorException(
                step_name=JOB_STEP_DOWNLOAD_METRICS,
                reason=f'No downloader available for storage class '
                       f'\'{storage.__class__}\''
            )
        return downloader(job_id, storage, results_folder_path)

    def _upload_job_results_s3(self, job_id, storage, results_folder_path):
        access = storage.access
        prefix = access.prefix
        bucket_name = access.bucket_name

        if prefix:
            s3_folder_path = os.path.join(prefix, job_id)
        else:
            s3_folder_path = job_id

        _LOG.debug(f'Listing objects in bucket \'{bucket_name}\'. '
                   f'Prefix: \'{prefix}\'')

        files = [y for x in os.walk(results_folder_path)
                 for y in glob(os.path.join(x[0], '*.jsonl'))]

        for file in files:
            file_key = file.replace(results_folder_path, '').strip('/')
            s3_file_key = os.path.join(s3_folder_path, file_key)
            with open(file, 'r') as f:
                body = f.read()
            self.s3_client.put_object(
                bucket_name=bucket_name,
                object_name=s3_file_key,
                body=body
            )

    @staticmethod
    def _build_s3_paths(prefix, scan_customer, scan_clouds, scan_tenants):
        path_lst = []
        paths = []
        if prefix:
            path_lst.append(prefix)
        if scan_customer:
            path_lst.append(scan_customer)
            for scan_cloud in scan_clouds:
                if scan_tenants and ALL not in scan_tenants:
                    for tenant in scan_tenants:
                        tenant_path = path_lst.copy()
                        tenant_path.append(scan_cloud)
                        tenant_path.append(tenant)
                        paths.append('/'.join(tenant_path))
                else:
                    cloud_path = path_lst.copy()
                    cloud_path.append(scan_cloud)
                    paths.append('/'.join(cloud_path))
        if not paths and path_lst:
            paths.append('/'.join(path_lst))
        return paths

    def get_scan_dates_list(self, scan_from_date: str = None,
                            scan_to_date: str = None):
        if not scan_from_date:
            _LOG.warning(f'No start date provided.')
            return
        try:
            start_dt = datetime.strptime(scan_from_date, DATE_FORMAT)
        except ValueError:
            _LOG.warning(f'Invalid scan start date: {scan_from_date} '
                         f'must have %Y_%m_%d pattern.')
            return

        try:
            end_dt = datetime.strptime(scan_to_date, DATE_FORMAT)
        except (ValueError, TypeError):
            _LOG.warning(f'Invalid/Empty scan stop date: {scan_from_date} '
                         f'must have %Y_%m_%d pattern.')
            end_d = date.today() + timedelta(days=1)
            end_dt = datetime.combine(end_d, datetime.min.time())
            _LOG.debug(f'Default stop date will be used: {end_dt.isoformat()}')

        dt_list = self.__date_range(start_date=start_dt, end_date=end_dt)
        return [dt.strftime(DATE_FORMAT) for dt in dt_list]

    @staticmethod
    def __date_range(start_date, end_date):
        return [start_date + timedelta(n)
                for n in range(int((end_date - start_date).days) + 1)]
