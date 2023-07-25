from modular_sdk.models.parent import Parent

from commons.constants import JOB_STEP_INITIALIZATION, TENANT_LICENSE_KEY_ATTR
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from commons.time_helper import utc_iso
from models.job import Job, JobStatusEnum
from models.license import License
from models.storage import Storage
from services import SERVICE_PROVIDER
from services.algorithm_service import AlgorithmService
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.metrics_service import MetricsService
from services.mocked_data_service import MockedDataService
from services.os_service import OSService
from services.recomendation_service import RecommendationService
from services.reformat_service import ReformatService
from services.resize.resize_service import ResizeService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.schedule.schedule_service import ScheduleService
from services.setting_service import SettingsService
from services.storage_service import StorageService

algorithm_service: AlgorithmService = SERVICE_PROVIDER.algorithm_service()
storage_service: StorageService = SERVICE_PROVIDER.storage_service()
job_service: JobService = SERVICE_PROVIDER.job_service()
environment_service: EnvironmentService = SERVICE_PROVIDER.environment_service()
os_service: OSService = SERVICE_PROVIDER.os_service()
metrics_service: MetricsService = SERVICE_PROVIDER.metrics_service()
schedule_service: ScheduleService = SERVICE_PROVIDER.schedule_service()
resize_service: ResizeService = SERVICE_PROVIDER.resize_service()
reformat_service: ReformatService = SERVICE_PROVIDER.reformat_service()
recommendation_service: RecommendationService = SERVICE_PROVIDER. \
    recommendation_service()
settings_service: SettingsService = SERVICE_PROVIDER.settings_service()
parent_service: RightSizerParentService = SERVICE_PROVIDER.parent_service()
mocked_data_service: MockedDataService = SERVICE_PROVIDER.mocked_data_service()
application_service: RightSizerApplicationService = SERVICE_PROVIDER. \
    application_service()
license_service: LicenseService = SERVICE_PROVIDER.license_service()
license_manager_service: LicenseManagerService = SERVICE_PROVIDER. \
    license_manager_service()

_LOG = get_logger('r8s-executor')

JOB_ID = environment_service.get_batch_job_id()
SCAN_CUSTOMER = environment_service.get_scan_customer()
SCAN_TENANTS = environment_service.get_scan_tenants()
SCAN_TIMESTAMP = environment_service.get_scan_timestamp()
SCAN_CLOUDS = environment_service.get_scan_clouds()
LICENSE_KEY = environment_service.get_license_key()


def set_job_fail_reason(exception: Exception, licensed: bool):
    if isinstance(exception, ExecutorException):
        reason = str(exception)
    else:
        reason = f'{type(exception).__name__}: {str(exception)}'
    _LOG.debug(f'Setting job {JOB_ID} fail reason to \'{reason}\'')
    job = job_service.get_by_id(object_id=JOB_ID)
    if job:
        job.status = JobStatusEnum.JOB_FAILED_STATUS.value
        job.fail_reason = reason
        job.save()
        _LOG.debug('Job reason was saved.')
    if licensed:
        _LOG.debug(f'Updating job status in LM')
        license_manager_service.update_job_in_license_manager(
            job_id=JOB_ID,
            created_at=utc_iso(job.created_at),
            started_at=utc_iso(job.started_at),
            stopped_at=utc_iso(job.stopped_at),
            status=job.status.value
        )


def submit_licensed_job(parent: Parent, scan_tenants: list, license_: License):
    if not scan_tenants or len(scan_tenants) != 1:
        _LOG.error(f'Exactly 1 tenant must be specified for licensed jobs.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Exactly 1 tenant must be specified for licensed jobs.'
        )
    customer = parent.customer_id
    tenant_license_key = license_.customers.get(customer, {}).get(
        TENANT_LICENSE_KEY_ATTR)
    algorithm_name = parent.meta.algorithm

    algorithm_map = {
        tenant_license_key: algorithm_name
    }

    licensed_job = license_manager_service.instantiate_licensed_job_dto(
        job_id=JOB_ID,
        customer=customer,
        tenant=scan_tenants[0],
        algorithm_map=algorithm_map
    )
    if not licensed_job:
        reason = 'Job execution could not be granted.'
        raise ExecutorException(reason=reason,
                                step_name=JOB_STEP_INITIALIZATION)
    return licensed_job


def main():
    _LOG.debug(f'Creating directories')
    work_dir, metrics_dir, reports_dir = \
        os_service.create_work_dirs(job_id=JOB_ID)

    _LOG.debug(f'Describing job with id \'{JOB_ID}\'')
    job: Job = job_service.get_by_id(object_id=JOB_ID)

    if not job:
        _LOG.error(f'Job with id \'{JOB_ID}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Job with id \'{JOB_ID}\' does not exist'
        )

    parent_id = job.parent_id
    parent = parent_service.get_parent_by_id(
        parent_id=parent_id)
    _LOG.debug(f'Parent: \'{parent_id}\'')
    if not parent or parent.is_deleted:
        _LOG.error(f'Parent \'{parent_id}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Parent \'{parent_id}\' does not exist'
        )

    licensed_job_data = None
    if LICENSE_KEY:
        license_: License = license_service.get_license(license_id=LICENSE_KEY)
        licensed_job_data = submit_licensed_job(
            parent=parent,
            license_=license_,
            scan_tenants=SCAN_TENANTS)

    _LOG.debug(f'Setting job status to RUNNING')
    job = job_service.set_status(job=job,
                                 status=JobStatusEnum.JOB_RUNNING_STATUS.value,
                                 licensed=bool(LICENSE_KEY))

    parent_meta = parent_service.get_parent_meta(
        parent=parent
    )
    if parent_meta.cloud != 'ALL_CLOUDS':
        SCAN_CLOUDS = [parent_meta.cloud.lower()]
    application_id = parent.application_id
    application = application_service.get_application_by_id(
        application_id=application_id)
    if not application or application.is_deleted:
        _LOG.error(f'Application \'{parent_id}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Application \'{parent_id}\' does not exist'
        )
    application_meta = application_service.get_application_meta(
        application=application
    )
    algorithm_name = parent_meta.algorithm
    algorithm = algorithm_service.get_by_name(name=algorithm_name)
    _LOG.debug(f'Algorithm: \'{algorithm_name}\'')
    if not algorithm:
        _LOG.error(f'Application \'{application_id}\' does not have algorithm '
                   f'specified')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Application \'{application_id}\' does not have algorithm '
                   f'specified'
        )
    if licensed_job_data:
        _LOG.debug(f'Syncing algorithm with licensed job data')
        algorithm_service.update_from_licensed_job(
            algorithm=algorithm,
            licensed_job=licensed_job_data
        )
    if not algorithm.checksum_matches():
        _LOG.error(f'Algorithm \'{algorithm.name}\' checksum '
                   f'verification failed.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Algorithm \'{algorithm.name}\' checksum '
                   f'verification failed.'
        )
    input_storage_name = application_meta.input_storage
    _LOG.debug(f'Input storage: \'{input_storage_name}\'')
    input_storage: Storage = storage_service.get_by_name(
        name=input_storage_name)
    if not input_storage:
        _LOG.error(f'Input storage \'{input_storage_name}\' does not exist.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Input storage \'{input_storage_name}\' does not exist.'
        )

    output_storage_name = application_meta.output_storage
    _LOG.debug(f'Output storage: \'{output_storage_name}\'')
    output_storage: Storage = storage_service.get_by_name(
        name=output_storage_name)
    if not output_storage:
        _LOG.error(f'Output storage \'{output_storage_name}\' does not exist.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Output storage \'{output_storage_name}\' does not exist.'
        )

    _LOG.debug(f'Resolving tenants to scan')
    tenants_to_scan = parent_service.resolve_scan_tenants_list(
        scan_tenants=SCAN_TENANTS,
        parent=parent
    )
    _LOG.debug(f'Tenants to process \'{tenants_to_scan}\'')

    _LOG.info(
        f'Downloading metrics from storage \'{input_storage_name}\'')
    storage_service.download_metrics(data_source=input_storage,
                                     output_path=metrics_dir,
                                     scan_customer=SCAN_CUSTOMER,
                                     scan_clouds=SCAN_CLOUDS,
                                     scan_tenants=tenants_to_scan,  # temporary
                                     scan_timestamp=SCAN_TIMESTAMP)

    _LOG.info(f'Loading instances meta')
    instance_meta_mapping = metrics_service.read_meta(
        metrics_folder=metrics_dir)

    _LOG.info(f'Merging metric files by timestamp')
    metrics_service.merge_metric_files(
        metrics_folder_path=metrics_dir,
        algorithm=algorithm)

    _LOG.info(f'Extracting metric files')
    metric_file_paths = os_service.extract_metric_files(
        algorithm=algorithm, metrics_folder_path=metrics_dir)
    _LOG.debug(f'Reformatting metrics to relative metric values')

    for metric_file_path in metric_file_paths.copy():
        try:
            _LOG.debug(f'Validating metric file: \'{metric_file_path}\'')
            metrics_service.validate_metric_file(
                algorithm=algorithm,
                metric_file_path=metric_file_path)
            _LOG.debug(f'Reformatting metric file: \'{metric_file_path}\'')
            reformat_service.to_relative_values(
                metrics_file_path=metric_file_path,
                algorithm=algorithm)
        except Exception as e:
            metric_file_paths.remove(metric_file_path)
            recommendation_service.dump_error_report(
                reports_dir=reports_dir,
                metric_file_path=metric_file_path,
                exception=e)

    if environment_service.is_debug():
        _LOG.info(f'Searching for instances to replace with mocked data')
        mocked_data_service.process(
            instance_meta_mapping=instance_meta_mapping,
            metric_file_paths=metric_file_paths
        )

    _LOG.info(f'Metric file paths to process: \'{metric_file_paths}\'')
    for index, metric_file_path in enumerate(metric_file_paths, start=1):
        _LOG.debug(
            f'Processing {index}/{len(metric_file_paths)} instance: '
            f'\'{metric_file_path}\'')
        result = recommendation_service.process_instance(
            metric_file_path=metric_file_path,
            algorithm=algorithm,
            reports_dir=reports_dir,
            instance_meta_mapping=instance_meta_mapping,
            parent_meta=parent_meta
        )
        _LOG.debug(f'Result: {result}')
    _LOG.debug(f'Uploading job results to storage \'{output_storage_name}\'')
    storage_service.upload_job_results(
        job_id=JOB_ID,
        results_folder_path=reports_dir,
        storage=output_storage
    )

    _LOG.debug(f'Job {JOB_ID} has finished successfully')
    _LOG.debug(f'Setting job state to SUCCEEDED')
    job_service.set_status(job=job,
                           status=JobStatusEnum.JOB_SUCCEEDED_STATUS.value,
                           licensed=bool(LICENSE_KEY))
    os_service.clean_workdir(work_dir=work_dir)


if __name__ == '__main__':
    try:
        main()
    except Exception as exception:
        set_job_fail_reason(exception=exception, licensed=bool(LICENSE_KEY))
        raise
