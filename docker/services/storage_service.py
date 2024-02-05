import os
from datetime import datetime, timedelta, date
from glob import glob
import concurrent
import itertools

from typing import List, Dict, Tuple

from bson import ObjectId
from bson.errors import InvalidId
from mongoengine.errors import DoesNotExist, ValidationError

from commons.constants import SERVICE_ATTR, \
    JOB_STEP_DOWNLOAD_METRICS, CSV_EXTENSION, META_FILE_NAME, ALL
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.recommendation_history import RecommendationHistory
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

    @profiler(execution_step=f's3_download_tenant_metrics')
    def download_metrics(self, data_source: Storage, output_path: str,
                         resource_type, scan_customer, scan_clouds,
                         scan_tenants, scan_from_date, scan_to_date,
                         max_days, min_days, recommendations_map: dict,
                         force_rescan: bool):
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
        return downloader(data_source, output_path, resource_type,
                          scan_customer, scan_clouds, scan_tenants,
                          scan_from_date, scan_to_date, max_days, min_days,
                          recommendations_map, force_rescan)

    def _download_metrics_s3(self, data_source: S3Storage, output_path,
                             resource_type, scan_customer, scan_clouds,
                             scan_tenants, scan_from_date=None,
                             scan_to_date=None, max_days=None, min_days=None,
                             recommendations_map: dict = None,
                             force_rescan=False):
        access = data_source.access
        prefix = access.prefix
        bucket_name = access.bucket_name

        paths = self._build_s3_paths(prefix=prefix,
                                     resource_type=resource_type,
                                     scan_customer=scan_customer,
                                     scan_clouds=scan_clouds,
                                     scan_tenants=scan_tenants)

        _LOG.debug(f'Listing objects in bucket \'{bucket_name}\'. '
                   f'from paths: \'{paths}\'')
        s3_keys = []
        if paths:
            for path in paths:
                files = self.s3_client.list_objects(bucket_name=bucket_name,
                                                    prefix=path)
                if files:
                    s3_keys.extend(files)
        else:
            files = self.s3_client.list_objects(bucket_name=bucket_name)
            s3_keys.extend(files)
        s3_keys = [obj['Key'] for obj in s3_keys if
                   obj.get('Key').endswith(CSV_EXTENSION)
                   or obj.get('Key').endswith(f'/{META_FILE_NAME}')]

        if not scan_from_date and max_days:
            _LOG.debug(f'Start stan date is not specified. Going to use '
                       f'limitation from algorithm of {max_days} days')
            scan_start_dt = datetime.utcnow() - timedelta(days=max_days)
            scan_from_date = scan_start_dt.strftime(DATE_FORMAT)

        filter_only_dates = self.get_scan_dates_list(
            scan_from_date=scan_from_date,
            scan_to_date=scan_to_date
        )
        if filter_only_dates:
            s3_keys = [key for key in s3_keys if key.split('/')[-2]
                       in filter_only_dates]

        _LOG.debug(f'Dividing meta file keys from metric keys')
        s3_keys, meta_keys = self.divide_meta_files(
            s3_keys=s3_keys)

        # for instances with insufficient metrics data:
        # {instance_id: List[s3_key]}
        insufficient_map = {}
        # for instances that haven't been updated since last scan:
        # {instance_id: List[RecommendationHistory]}
        unchanged_map = {}

        if min_days and not force_rescan:
            _LOG.debug(f'Filtering objects by the amount of '
                       f'daily metric files. '
                       f'Minimum days required: {min_days}')
            s3_keys, insufficient_map = (
                self.filter_keys_by_occurrence_count(
                    s3_keys=s3_keys,
                    min_count=min_days
                ))
        if recommendations_map and not force_rescan:
            _LOG.debug(f'Filtering instances with metric updates')
            s3_keys, unchanged_map = self.filter_keys_without_updates(
                s3_keys=s3_keys,
                recommendations_map=recommendations_map
            )
        if insufficient_map and unchanged_map:
            unchanged_map = {instance_id: value for instance_id, value
                             in unchanged_map.items()
                             if instance_id not in insufficient_map}

        _LOG.debug(f'{len(s3_keys)} metric, {len(meta_keys)} meta '
                   f'files found, downloading')
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for s3_key in itertools.chain(meta_keys, s3_keys):
                path = s3_key.split('/')
                if len(path) > 0 and path[0] == prefix:
                    path = path[1:]
                path = '/'.join(path[:-1])
                output_folder_path = '/'.join((output_path, path))
                os.makedirs(output_folder_path, exist_ok=True)

                futures.append(executor.submit(
                    self.s3_client.download_file,
                    bucket_name=bucket_name,
                    full_file_name=s3_key,
                    output_folder_path=output_folder_path
                ))
        return insufficient_map, unchanged_map

    @profiler(execution_step=f's3_upload_job_results')
    def upload_job_results(self, job_id, storage: Storage,
                           results_folder_path, tenant=None):
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
        return downloader(job_id, storage, results_folder_path, tenant)

    def _upload_job_results_s3(self, job_id, storage, results_folder_path,
                               tenant=None):
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
        if tenant:
            files = [file for file in files if file.split('/')[-2] == tenant]

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
    def _build_s3_paths(prefix, resource_type,
                        scan_customer, scan_clouds, scan_tenants):
        path_lst = []
        paths = []
        if prefix:
            path_lst.append(prefix)
        if resource_type:
            path_lst.append(resource_type.lower())
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
            _LOG.warning(f'Invalid/Empty scan stop date: {scan_to_date} '
                         f'must have {DATE_FORMAT} pattern.')
            end_d = date.today() + timedelta(days=1)
            end_dt = datetime.combine(end_d, datetime.min.time())
            _LOG.debug(f'Default stop date will be used: {end_dt.isoformat()}')

        dt_list = self.__date_range(start_date=start_dt, end_date=end_dt)
        return [dt.strftime(DATE_FORMAT) for dt in dt_list]

    @staticmethod
    def __date_range(start_date, end_date):
        return [start_date + timedelta(n)
                for n in range(int((end_date - start_date).days) + 1)]

    def upload_profile_log(self, job_id, storage: Storage, file_path):
        access = storage.access
        prefix = access.prefix
        bucket_name = access.bucket_name

        if prefix:
            s3_folder_path = os.path.join(prefix, job_id)
        else:
            s3_folder_path = job_id

        s3_file_key = os.path.join(s3_folder_path, file_path.split('/')[-1])
        with open(file_path, 'r') as f:
            body = f.read()

        self.s3_client.put_object(
            bucket_name=bucket_name,
            object_name=s3_file_key,
            body=body
        )

    @staticmethod
    def divide_meta_files(s3_keys: List[str]):
        meta_keys = []
        metric_keys = []
        for key in s3_keys:
            if key.endswith(META_FILE_NAME):
                meta_keys.append(key)
            elif key.endswith(CSV_EXTENSION):
                metric_keys.append(key)
        return metric_keys, meta_keys

    @staticmethod
    def filter_keys_by_occurrence_count(
            s3_keys: list, min_count: int) \
            -> Tuple[List[str], Dict[str, List[str]]]:
        instance_metrics_map = {}
        for s3_key in s3_keys:
            instance_id = s3_key.split('/')[-1].replace(CSV_EXTENSION, '')
            if instance_id not in instance_metrics_map:
                instance_metrics_map[instance_id] = [s3_key]
            else:
                instance_metrics_map[instance_id].append(s3_key)
        valid_instances_map = {}
        insufficient_metrics_map = {}
        for instance_id, keys in instance_metrics_map.items():
            if len(keys) >= min_count:
                valid_instances_map[instance_id] = keys
            else:
                insufficient_metrics_map[instance_id] = keys

        return list(itertools.chain.from_iterable(
            valid_instances_map.values())), insufficient_metrics_map

    def filter_keys_without_updates(
            self, s3_keys: List[str],
            recommendations_map: Dict[str, List[RecommendationHistory]]
    ) -> Tuple[List[dict], Dict[str, List[RecommendationHistory]]]:
        result: Dict[str, List[str]] = {}
        unchanged_map: Dict[str: List[RecommendationHistory]] = {}
        for s3_key in sorted(s3_keys, reverse=True):
            try:
                object_dt, instance_id = self.__parse_path(path=s3_key)
            except (ValueError, IndexError, ValueError) as e:
                _LOG.warning(f'Key with invalid format will '
                             f'be skipped: {s3_key}. Error: {e}')
                continue
            if instance_id in result:
                result[instance_id].append(s3_key)
                continue
            past_recommendations = recommendations_map.get(instance_id)
            if not past_recommendations:
                result[instance_id] = [s3_key]
                continue
            last_captured_date = (past_recommendations[0].
                                  last_metric_capture_date)
            if not last_captured_date or last_captured_date < object_dt:
                result[instance_id] = [s3_key]
            else:
                unchanged_map[instance_id] = past_recommendations

        s3_keys = list(itertools.chain.from_iterable(result.values()))
        return s3_keys, unchanged_map

    @staticmethod
    def __parse_path(path: str) -> tuple[datetime, str]:
        *_, date_str, file_name = path.split('/')
        instance_id = file_name.replace(CSV_EXTENSION, '')
        metric_dt = datetime.strptime(date_str, DATE_FORMAT)
        return metric_dt, instance_id
