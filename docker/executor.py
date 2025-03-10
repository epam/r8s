import os.path
from typing import Tuple, Optional

from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent
from modular_sdk.commons.constants import ParentType

from commons.constants import (JOB_STEP_INITIALIZATION,
                               TENANT_LICENSE_KEY_ATTR, PROFILE_LOG_PATH,
                               JOB_STEP_INITIALIZE_ALGORITHM, RESOURCE_TYPE_VM,
                               RESOURCE_TYPE_ATTR)
from commons.exception import ExecutorException, LicenseForbiddenException
from commons.log_helper import get_logger
from commons.profiler import profiler
from models.algorithm import Algorithm
from models.job import Job, JobStatusEnum, JobTenantStatusEnum
from models.license import License
from models.parent_attributes import LicensesParentMeta
from models.recommendation_history import RecommendationTypeEnum
from models.storage import Storage
from services import SERVICE_PROVIDER
from services.algorithm_service import AlgorithmService
from services.defect_dojo_service import DefectDojoService
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.meta_service import MetaService
from services.metrics_service import MetricsService, \
    INSUFFICIENT_DATA_ERROR_TEMPLATE
from services.mocked_data_service import MockedDataService
from services.os_service import OSService
from services.recomendation_service import RecommendationService
from services.recommendation_history_service import \
    RecommendationHistoryService
from services.reformat_service import ReformatService
from services.resize.resize_service import ResizeService
from services.resource_group_service import ResourceGroupService
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
recommendation_history_service: RecommendationHistoryService = (
    SERVICE_PROVIDER.recommendation_history_service())
meta_service: MetaService = SERVICE_PROVIDER.meta_service()
resource_group_service: ResourceGroupService = (
    SERVICE_PROVIDER.resource_group_service())

_LOG = get_logger('r8s-executor')

JOB_ID = environment_service.get_batch_job_id()
SCAN_FROM_DATE = environment_service.get_scan_from_date()
SCAN_TO_DATE = environment_service.get_scan_to_date()
APPLICATION_ID = environment_service.get_application_id()
LICENSED_APPLICATION_ID = environment_service.get_licensed_application_id()
PARENT_ID = environment_service.get_licensed_parent_id()

DOJO_APPLICATION_MAP = {}


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
def submit_licensed_job(application: Application, tenant_name: str,
                        license_: License):
    customer = application.customer_id
    tenant_license_key = license_.customers.get(customer, {}).get(
        TENANT_LICENSE_KEY_ATTR)
    algorithm_name = application.meta.algorithm_map[RESOURCE_TYPE_VM]

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
                             parent_meta: LicensesParentMeta,
                             application: Application,
                             licensed_application: Application,
                             algorithm: Algorithm,
                             tenant: str,
                             dojo_application: Application = None,
                             dojo_parent: Parent = None):
    tenant_recommendations = []

    _LOG.info(f'Downloading metrics from storage \'{input_storage.name}\', '
              f'for tenant: {tenant}, for resource type: '
              f'{algorithm.resource_type}')

    force_rescan = environment_service.force_rescan()
    if not force_rescan:
        _LOG.debug(f'Querying for past tenant {tenant} recommendations.')
        recommendations_map = (recommendation_history_service.
                               get_tenant_recommendation(tenant=tenant))
    else:
        _LOG.debug('Force rescan enabled, querying for past tenant '
                   'recommendations is omitted')
        recommendations_map = {}

    cloud = licensed_application.meta.cloud.lower()

    insufficient_map, unchanged_map = storage_service.download_metrics(
        data_source=input_storage,
        output_path=metrics_dir,
        resource_type=algorithm.resource_type,
        scan_customer=licensed_application.customer_id,
        scan_clouds=[cloud],
        scan_tenants=[tenant],
        scan_from_date=SCAN_FROM_DATE,
        scan_to_date=SCAN_TO_DATE,
        max_days=algorithm.recommendation_settings.max_days,
        min_days=algorithm.recommendation_settings.min_allowed_days,
        recommendations_map=recommendations_map,
        force_rescan=force_rescan)

    tenant_folder_path = os.path.join(
        metrics_dir,
        algorithm.resource_type.lower(),
        licensed_application.customer_id,
        cloud,
        tenant)

    _LOG.info('Loading instances meta for tenant')
    instance_meta_mapping = metrics_service.read_meta(
        metrics_folder=tenant_folder_path)

    _LOG.info('Merging metric files by date')
    metrics_service.merge_metric_files(
        metrics_folder_path=tenant_folder_path,
        algorithm=algorithm)

    _LOG.info('Extracting tenant metric files')
    metric_file_paths = os_service.extract_metric_files(
        algorithm=algorithm, metrics_folder_path=tenant_folder_path)

    _LOG.debug('Reformatting metrics to relative metric values')
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
        _LOG.info('Searching for instances to replace with mocked data')
        mocked_data_service.process(
            instance_meta_mapping=instance_meta_mapping,
            metric_file_paths=metric_file_paths
        )

    if insufficient_map:
        _LOG.info(f'Dumping {len(insufficient_map.keys())} instances '
                  f'with insufficient metrics: '
                  f'{list(insufficient_map.keys())}')
        for instance_id, metric_s3_keys in insufficient_map.items():
            _LOG.debug(f'Dumping instance {instance_id} result')
            recommendation_service.dump_error_report(
                reports_dir=reports_dir,
                metric_file_path=metric_s3_keys[0],
                exception=ExecutorException(
                    step_name=JOB_STEP_INITIALIZE_ALGORITHM,
                    reason=INSUFFICIENT_DATA_ERROR_TEMPLATE.format(
                        days=algorithm.recommendation_settings.min_allowed_days
                    )
                )
            )
    if unchanged_map:
        _LOG.info(f'Dumping instances with unchanged metrics from last '
                  f'scan: {list(unchanged_map.keys())}')
        for instance_id, past_recommendations in unchanged_map.items():
            _LOG.debug(f'Dumping instance {instance_id} result')
            recommendation_service.dump_reports_from_recommendations(
                reports_dir=reports_dir,
                cloud=cloud.lower(),
                recommendations=past_recommendations
            )

    app_meta = application_service.get_application_meta(
        application=application)

    group_resources_mapping = {}
    if app_meta.group_policies:
        _LOG.debug('Processing application group policies')
        group_resources_mapping, metric_file_paths = (
            recommendation_service.divide_by_group_policies(
                metric_file_paths=metric_file_paths,
                group_policies=app_meta.group_policies,
                instance_meta_mapping=instance_meta_mapping
            ))

    if group_resources_mapping:
        _LOG.debug(f'Group resources: {group_resources_mapping}')
        for group_id, group_resources in group_resources_mapping.items():
            group = application_service.get_group_policy(
                meta=app_meta,
                group_id=group_id
            )
            if not group:
                _LOG.warning(f'Group policy {group_id} does not found. '
                             f'Resources in group will be processed '
                             f'as individual resources')
                metric_file_paths.extend(group_resources)
            _LOG.debug(f'Processing group {group_id} resources')
            for tag_value, tag_resources in group_resources.items():
                _LOG.debug(f'Processing group tag {tag_value}')
                recommendation_service.process_group_resources(
                    group_id=tag_value,
                    group_policy=group,
                    metric_file_paths=tag_resources,
                    algorithm=algorithm,
                    reports_dir=reports_dir,
                    instance_meta_mapping=instance_meta_mapping
                )

    dojo_service = None
    if dojo_application and dojo_parent:
        try:
            _LOG.debug(f'Initializing dojo service')
            dojo_service = DefectDojoService(
                ssm_service=SERVICE_PROVIDER.ssm_service(),
                application=dojo_application
            )
        except ExecutorException as e:
            _LOG.error(str(e))
        except Exception as e:
            _LOG.error(f'Unexpected exception occurred on '
                       f'Dojo initialization: {e}')

    group_results = {}
    group_history_items = []
    instance_region_mapping = {}
    _LOG.info(f'Tenant {tenant} metric file paths to '
              f'process: \'{metric_file_paths}\'')
    for index, metric_file_path in enumerate(metric_file_paths, start=1):
        _LOG.debug(
            f'Processing {index}/{len(metric_file_paths)} instance: '
            f'\'{metric_file_path}\'')
        result, history_items = recommendation_service.process_instance(
            metric_file_path=metric_file_path,
            algorithm=algorithm,
            reports_dir=reports_dir,
            instance_meta_mapping=instance_meta_mapping,
            parent_meta=parent_meta
        )
        _LOG.debug(f'Result: {result}')

        _, _, _, region, _, resource_id = (
            recommendation_service.parse_folders(
                metric_file_path=metric_file_path
            ))
        instance_region_mapping[resource_id] = region

        instance_meta = instance_meta_mapping.get(resource_id)
        if group_id := meta_service.get_resource_group_id(
                instance_meta=instance_meta):
            _LOG.debug('Group item detected. Recommendations wont be '
                       'saved until comparison.')
            if group_id not in group_results:
                group_results[group_id] = [result]
            else:
                group_results[group_id].append(result)
            if history_items:
                group_history_items.extend(history_items)
        else:
            _LOG.debug('Saving independent resource recommendation')
            recommendation_service.save_report(
                reports_dir=reports_dir,
                customer=licensed_application.customer_id,
                cloud=cloud,
                tenant=tenant,
                region=region,
                item=result
            )
            if history_items:
                tenant_recommendations.extend(history_items)
                recommendation_service.save_history_items(
                    history_items=history_items)

    tenant_recommendations = [i for i in tenant_recommendations if
                              i.recommendation_type !=
                              RecommendationTypeEnum.ACTION_EMPTY]
    if dojo_service and tenant_recommendations:
        try:
            _LOG.debug(f'Pushing recommendations to Dojo')
            dojo_service.push_findings(
                parent=dojo_parent,
                recommendation_history_items=tenant_recommendations
            )
        except ExecutorException as e:
            _LOG.error(str(e))
        except Exception as e:
            _LOG.error(f'Unexpected exception occurred on '
                       f'Dojo upload: {e}')

    if group_results:
        _LOG.debug('Filtering contradictory recommendations '
                   'inside resource groups')
        filtered_reports, filtered_history = resource_group_service.filter(
            group_results=group_results,
            group_history_items=group_history_items
        )
        _LOG.debug('Saving group results')
        for report in filtered_reports:
            recommendation_service.save_report(
                reports_dir=reports_dir,
                customer=licensed_application.customer_id,
                cloud=cloud,
                tenant=tenant,
                region=instance_region_mapping.get(report.get('resource_id')),
                item=report
            )
        _LOG.debug('Saving group result recommendation')
        recommendation_service.save_history_items(
            history_items=filtered_history)

    _LOG.debug(f'Uploading job results to storage \'{output_storage.name}\'')
    storage_service.upload_job_results(
        job_id=JOB_ID,
        results_folder_path=reports_dir,
        storage=output_storage,
        tenant=tenant
    )


def get_dojo_tenant_config(customer_name: str,
        tenant_name:str) -> Tuple[Optional[Application], Optional[Parent]]:
    _LOG.debug(f'Describing Dojo parent for tenant {tenant_name}')
    dojo_parent = parent_service.get_linked_parent(
        tenant_name=tenant_name,
        customer_name=customer_name,
        cloud=None,
        type_=ParentType.RIGHTSIZER_SIEM_DEFECT_DOJO
    )
    if not dojo_parent:
        _LOG.debug(f'No dojo parent found for tenant {tenant_name}')
        return None, None

    _LOG.debug(f'Dojo parent to be used with tenant {tenant_name}: '
               f'{dojo_parent.parent_id}. '
               f'Describing linked application '
               f'{dojo_parent.application_id}')
    if dojo_parent.application_id in DOJO_APPLICATION_MAP:
        _LOG.debug(f'Using cached application '
                   f'{dojo_parent.application_id}')
        dojo_application = DOJO_APPLICATION_MAP[
            dojo_parent.application_id]
    else:
        _LOG.debug(f'Describing application '
                   f'{dojo_parent.application_id}')
        dojo_application = application_service.get_application_by_id(
            application_id=dojo_parent.application_id
        )
        if not dojo_application:
            _LOG.debug(f'Parent {dojo_parent.parent_id} '
                       f'application {dojo_parent.application_id} '
                       f'does not exist')
        DOJO_APPLICATION_MAP[dojo_parent.application_id] = (
            dojo_application)

    if dojo_application and dojo_parent:
        return dojo_application, dojo_parent
    return None, None


def main():
    _LOG.debug('Creating directories')
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

    _LOG.debug('Setting job status to RUNNING')
    job = job_service.set_status(
        job=job,
        status=JobStatusEnum.JOB_RUNNING_STATUS.value)

    application = application_service.get_application_by_id(
        application_id=APPLICATION_ID
    )
    _LOG.debug(f'RIGHTSIZER Application: {APPLICATION_ID}')
    if not application:
        _LOG.error(f'Application \'{APPLICATION_ID}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Application \'{APPLICATION_ID}\' does not exist'
        )

    scan_tenants = job_service.get_scan_tenants(job=job)
    licensed_application = application_service.get_application_by_id(
        application_id=LICENSED_APPLICATION_ID)
    _LOG.debug(f'Application: \'{LICENSED_APPLICATION_ID}\'')
    if not licensed_application or licensed_application.is_deleted:
        _LOG.error(f'Application \'{LICENSED_APPLICATION_ID}\' does not exist')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Application \'{LICENSED_APPLICATION_ID}\' does not exist'
        )

    licensed_application_meta = application_service.get_application_meta(
        application=licensed_application)
    license_key = licensed_application_meta.license_key

    host_application = application_service.get_host_application(
        customer=licensed_application.customer_id)
    if not host_application:
        _LOG.error(f'Host application for licenses application '
                   f'{LICENSED_APPLICATION_ID} not found')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Host application for licenses application '
                   f'{LICENSED_APPLICATION_ID} not found'
        )
    host_application_meta = application_service.get_application_meta(
        application=host_application
    )
    algorithm_name_map = licensed_application_meta.algorithm_map.as_dict()
    algorithm_map = {}

    for resource_type, algorithm_name in algorithm_name_map.items():
        algorithm_obj = algorithm_service.get_by_name(name=algorithm_name)
        _LOG.debug(f'Algorithm: \'{algorithm_name}\'')
        if not algorithm_obj:
            _LOG.error(f'Algorithm \'{algorithm_name}\' not found')
            raise ExecutorException(
                step_name=JOB_STEP_INITIALIZATION,
                reason=f'Algorithm \'{algorithm_name}\' not found'
            )
        algorithm_map[resource_type] = algorithm_obj

    input_storage_name = host_application_meta.input_storage
    _LOG.debug(f'Input storage: \'{input_storage_name}\'')
    input_storage: Storage = storage_service.get_by_name(
        name=input_storage_name)
    if not input_storage:
        _LOG.error(f'Input storage \'{input_storage_name}\' does not exist.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Input storage \'{input_storage_name}\' does not exist.'
        )

    output_storage_name = host_application_meta.output_storage
    _LOG.debug(f'Output storage: \'{output_storage_name}\'')
    output_storage: Storage = storage_service.get_by_name(
        name=output_storage_name)
    if not output_storage:
        _LOG.error(f'Output storage \'{output_storage_name}\' does not exist.')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Output storage \'{output_storage_name}\' does not exist.'
        )

    _LOG.info(f'Resolving RIGHTSIZER_LICENSES parents for application '
              f'{LICENSED_APPLICATION_ID}')
    parents = parent_service.get_job_parents(
        application_id=LICENSED_APPLICATION_ID,
        parent_id=PARENT_ID
    )
    if not parents:
        _LOG.error(f'Can\'t resolve RIGHTSIZER_LICENSES parents for license '
                   f'application: \'{LICENSED_APPLICATION_ID}\'')
        raise ExecutorException(
            step_name=JOB_STEP_INITIALIZATION,
            reason=f'Can\'t resolve RIGHTSIZER_LICENSES parents for license '
                   f'application: \'{LICENSED_APPLICATION_ID}\''
        )
    tenant_meta_map = parent_service.resolve_tenant_parent_meta_map(
        parents=parents)

    _LOG.debug(f'Describing License \'{license_key}\'')
    license_: License = license_service.get_license(license_id=license_key)


    for tenant in scan_tenants:
        try:
            _LOG.info(f'Processing tenant {tenant}')

            _LOG.debug(f'Submitting licensed job for tenant {tenant}')
            licensed_job_data = submit_licensed_job(
                application=licensed_application,
                license_=license_,
                tenant_name=tenant)
            for algorithm in algorithm_map.values():
                _LOG.debug(f'Syncing licensed algorithm from license '
                           f'{license_.license_key}')
                algorithm_service.update_from_licensed_job(
                    algorithm=algorithm,
                    licensed_job=licensed_job_data
                )

            dojo_application, dojo_parent = get_dojo_tenant_config(
                customer_name=licensed_application.customer_id,
                tenant_name=tenant
            )

            for algorithm in algorithm_map.values():
                process_tenant_instances(
                    metrics_dir=metrics_dir,
                    reports_dir=reports_dir,
                    input_storage=input_storage,
                    output_storage=output_storage,
                    parent_meta=tenant_meta_map[tenant],
                    application=application,
                    licensed_application=licensed_application,
                    algorithm=algorithm,
                    tenant=tenant,
                    dojo_application=dojo_application,
                    dojo_parent=dojo_parent
                )

            _LOG.info(f'Setting tenant status to "SUCCEEDED"')
            job_service.set_licensed_job_status(
                job=job,
                tenant=tenant,
                status=JobTenantStatusEnum.TENANT_SUCCEEDED_STATUS,
                customer=licensed_application.customer_id
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
    _LOG.debug('Setting job state to SUCCEEDED')
    job_service.set_status(job=job,
                           status=JobStatusEnum.JOB_SUCCEEDED_STATUS.value)

    if os.path.exists(PROFILE_LOG_PATH):
        _LOG.debug('Uploading profile log')
        storage_service.upload_profile_log(
            storage=output_storage,
            job_id=JOB_ID,
            file_path=PROFILE_LOG_PATH
        )
    _LOG.debug('Cleaning workdir')
    os_service.clean_workdir(work_dir=work_dir)


if __name__ == '__main__':
    try:
        main()
    except Exception as exception:
        set_job_fail_reason(exception=exception)
        raise
