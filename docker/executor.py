import os.path

from modular_sdk.models.parent import Parent

from commons.constants import (JOB_STEP_INITIALIZATION,
                               TENANT_LICENSE_KEY_ATTR, PROFILE_LOG_PATH)
from commons.exception import ExecutorException, LicenseForbiddenException
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.algorithm import Algorithm
from models.job import Job, JobStatusEnum, JobTenantStatusEnum
from models.license import License
from models.parent_attributes import ParentMeta
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
SCAN_FROM_DATE = environment_service.get_scan_from_date()
SCAN_TO_DATE = environment_service.get_scan_to_date()
PARENT_ID = environment_service.get_licensed_parent_id()


def set_job_fail_reason(exception: Exception):
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


@profiler(execution_step=f'lm_submit_job')
def submit_licensed_job(parent: Parent, tenant_name: str,
                        license_: License):
    customer = parent.customer_id
    tenant_license_key = license_.customers.get(customer, {}).get(
        TENANT_LICENSE_KEY_ATTR)
    algorithm_name = parent.meta.algorithm

    algorithm_map = {
        tenant_license_key: algorithm_name
    }
    try:
        licensed_job = license_manager_service.instantiate_licensed_job_dto(
            job_id=f'{JOB_ID}:{tenant_name}',
            customer=customer,
            tenant=tenant_name,
            algorithm_map=algorithm_map
        )
    except Exception as e:
        _LOG.warning(f'Job execution could not be granted '
                     f'for tenant {tenant_name}: {e}.')
        raise LicenseForbiddenException(
            tenant_name=tenant_name
        )
    return licensed_job


def process_tenant_instances(metrics_dir, reports_dir,
                             input_storage, output_storage,
                             parent_meta: ParentMeta,
                             licensed_parent: Parent,
                             algorithm: Algorithm,
                             license_: License,
                             customer: str,
                             tenant: str,
                             job: Job):
    _LOG.info(f'Downloading metrics from storage \'{input_storage.name}\', '
              f'for tenant: {tenant}')

    cloud = licensed_parent.meta.cloud.lower()
    storage_service.download_metrics(
        data_source=input_storage,
        output_path=metrics_dir,
        scan_customer=licensed_parent.customer_id,
        scan_clouds=[cloud],
        scan_tenants=[tenant],
        scan_from_date=SCAN_FROM_DATE,
        scan_to_date=SCAN_TO_DATE)

    tenant_folder_path = os.path.join(
        metrics_dir,
        customer,
        cloud,
        tenant)

    _LOG.info(f'Loading instances meta for tenant')
    instance_meta_mapping = metrics_service.read_meta(
        metrics_folder=tenant_folder_path)

    _LOG.info(f'Merging metric files by date')
    metrics_service.merge_metric_files(
        metrics_folder_path=tenant_folder_path,
        algorithm=algorithm)

    _LOG.info(f'Extracting tenant metric files')
    metric_file_paths = os_service.extract_metric_files(
        algorithm=algorithm, metrics_folder_path=tenant_folder_path)

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

    _LOG.debug(f'Submitting licensed job for tenant {tenant}')
    licensed_job_data = submit_licensed_job(
        parent=licensed_parent,
        license_=license_,
        tenant_name=tenant)

    _LOG.debug(f'Syncing licensed algorithm from license '
               f'{license_.license_key}')
    algorithm_service.update_from_licensed_job(
        algorithm=algorithm,
        licensed_job=licensed_job_data
    )

    _LOG.info(f'Tenant {tenant} metric file paths to '
              f'process: \'{metric_file_paths}\'')
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

    _LOG.debug(f'Uploading job results to storage \'{output_storage.name}\'')
    storage_service.upload_job_results(
        job_id=JOB_ID,
        results_folder_path=reports_dir,
        storage=output_storage,
        tenant=tenant
    )

    _LOG.info(f'Setting tenant status to "SUCCEEDED"')
    job_service.set_licensed_job_status(
        job=job,
        tenant=tenant,
        status=JobTenantStatusEnum.TENANT_SUCCEEDED_STATUS
    )


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

    _LOG.debug(f'Setting job status to RUNNING')
    job = job_service.set_status(
        job=job,
        status=JobStatusEnum.JOB_RUNNING_STATUS.value)

    scan_tenants = job_service.get_scan_tenants(job=job)
    licensed_parent_id = job.parent_id
    licensed_parent = parent_service.get_parent_by_id(
        parent_id=licensed_parent_id)
    _LOG.debug(f'Parent: \'{licensed_parent_id}\'')
    if not licensed_parent or licensed_parent.is_deleted:
        _LOG.error(f'Parent \'{licensed_parent_id}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Parent \'{licensed_parent_id}\' does not exist'
        )

    licensed_parent_meta = parent_service.get_parent_meta(
        parent=licensed_parent)
    license_key = licensed_parent_meta.license_key

    application_id = licensed_parent.application_id
    application = application_service.get_application_by_id(
        application_id=application_id)
    if not application or application.is_deleted:
        _LOG.error(f'Application \'{licensed_parent_id}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Application \'{licensed_parent_id}\' does not exist'
        )
    application_meta = application_service.get_application_meta(
        application=application
    )
    algorithm_name = licensed_parent_meta.algorithm
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

    _LOG.info(f'Resolving RIGHTSIZER parent for license')
    parent = parent_service.resolve(
        licensed_parent=licensed_parent,
        scan_tenants=scan_tenants
    )
    if not parent:
        _LOG.error(f'Can\'t resolve RIGHTSIZER parent for license '
                   f'\'{licensed_parent_id}\'. Shape rules won\'t be applied.')
        parent_meta = ParentMeta()
    else:
        parent_meta = parent_service.get_parent_meta(parent=parent)

    _LOG.debug(f'Describing License \'{license_key}\'')
    license_: License = license_service.get_license(license_id=license_key)

    for tenant in scan_tenants:
        try:
            _LOG.info(f'Processing tenant {tenant}')
            process_tenant_instances(
                metrics_dir=metrics_dir,
                reports_dir=reports_dir,
                input_storage=input_storage,
                output_storage=output_storage,
                parent_meta=parent_meta,
                licensed_parent=licensed_parent,
                algorithm=algorithm,
                license_=license_,
                customer=parent.customer_id,
                tenant=tenant,
                job=job
            )
        except LicenseForbiddenException as e:
            _LOG.error(e)
            job_service.set_licensed_job_status(
                job=job,
                tenant=tenant,
                status=JobTenantStatusEnum.TENANT_FAILED_STATUS
            )
        except Exception as e:
            _LOG.error(f'Unexpected error occurred while processing '
                       f'tenant {tenant}: {e}')
            job_service.set_licensed_job_status(
                job=job,
                tenant=tenant,
                status=JobTenantStatusEnum.TENANT_FAILED_STATUS
            )

    _LOG.debug(f'Job {JOB_ID} has finished successfully')
    _LOG.debug(f'Setting job state to SUCCEEDED')
    job_service.set_status(job=job,
                           status=JobStatusEnum.JOB_SUCCEEDED_STATUS.value)

    if os.path.exists(PROFILE_LOG_PATH):
        _LOG.debug(f'Uploading profile log')
        storage_service.upload_profile_log(
            storage=output_storage,
            job_id=JOB_ID,
            file_path=PROFILE_LOG_PATH
        )
    _LOG.debug(f'Cleaning workdir')
    os_service.clean_workdir(work_dir=work_dir)


if __name__ == '__main__':
    try:
        main()
    except Exception as exception:
        set_job_fail_reason(exception=exception)
        raise
