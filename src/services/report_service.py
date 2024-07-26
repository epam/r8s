from commons import build_response, RESPONSE_BAD_REQUEST_CODE
from commons.constants import CUSTOMER_ATTR, TENANT_ATTR, REGION_ATTR, \
    CLOUD_ATTR, REPORT_RECOMMENDATION_ATTR, \
    REPORT_RESOURCE_ID_ATTR
from commons.log_helper import get_logger
from models.job import Job
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.storage_service import StorageService

_LOG = get_logger('r8s-report-service')

HOURS_IN_MONTH = 730

GENERAL_ACTIONS_ATTR = 'general_actions'
RECOMMENDED_SHAPES_ATTR = 'recommended_shapes'
SCHEDULE_ATTR = 'schedule'

RESULT_INSTANCE_ATTRIBUTES = [REPORT_RESOURCE_ID_ATTR, CUSTOMER_ATTR,
                              CLOUD_ATTR, TENANT_ATTR, REGION_ATTR,
                              REPORT_RECOMMENDATION_ATTR,
                              GENERAL_ACTIONS_ATTR]
RECOMMENDATION_ATTRIBUTES = [
    SCHEDULE_ATTR, RECOMMENDED_SHAPES_ATTR
]


class ReportService:
    def __init__(self, storage_service: StorageService,
                 parent_service: RightSizerParentService,
                 application_service: RightSizerApplicationService):
        self.storage_service = storage_service
        self.parent_service = parent_service
        self.application_service = application_service

    def get_job_report(self, job: Job, detailed=None, customer=None,
                       cloud=None, tenant=None, region=None, instance_id=None):
        _LOG.debug(f'Describing job storage')
        job_storage = self.get_storage(customer=customer)

        job_results = self.storage_service.download_job_results(
            storage=job_storage,
            job_id=job.id,
            customer=customer,
            cloud=cloud,
            tenant=tenant,
            region=region,
        )
        _LOG.debug(f'Job results: {job_results}')

        if instance_id:
            _LOG.debug(f'Filtering job results by instance id: {instance_id}')
            job_results = [item for item in job_results
                           if item.get('instance_id') == instance_id]

        if detailed:
            _LOG.debug(f'Returning detailed results')
            return job_results

        _LOG.debug(f'Reformatting job results')
        reformatted = []
        for instance_data in job_results:
            instance_data = {k: v for k, v in instance_data.items()
                             if k in RESULT_INSTANCE_ATTRIBUTES}
            recommendation = instance_data.pop(REPORT_RECOMMENDATION_ATTR,
                                               None)
            recommendation = {k: v for k, v in recommendation.items()
                              if k in RECOMMENDATION_ATTRIBUTES}
            if not recommendation or not isinstance(recommendation, dict):
                return
            sizes = recommendation.get('recommended_shapes', [])
            size_names = [item['name'] for item in sizes]
            recommendation['recommended_shapes'] = size_names

            schedule = recommendation.get('schedule')
            readable_schedules = [self.get_readable_schedule(item)
                                  for item in schedule]
            readable_schedules = [schedule for schedule in readable_schedules
                                  if schedule]
            recommendation['schedule'] = readable_schedules
            instance_data.update(recommendation)
            _LOG.debug(f'Instance recommendation \'{instance_data}\'')
            reformatted.append(instance_data)
        _LOG.debug(f'Reformatted job results: \'{job_results}\'')
        return reformatted

    def get_download_report(self, job: Job, customer, tenant, region):
        _LOG.debug(f'Describing job storage')
        storage = self.get_storage(customer=customer)

        objects = self.storage_service.list_object_with_presigned_urls(
            storage=storage, job_id=job.id)

        result = []
        for file in objects:
            folders = file.get('Key').split('/')
            region_folder = folders[-1].replace('.jsonl', '')
            tenant_folder = folders[-2]
            cloud_folder = folders[-3]
            customer_folder = folders[-4]

            if customer and customer_folder != customer:
                continue
            if tenant and tenant_folder != tenant:
                continue
            if region and region_folder != region:
                continue

            presigned_url = file.get('presigned_url')
            last_updated = file.get('LastModified')
            item = {
                'customer': customer_folder,
                'cloud': cloud_folder,
                'tenant': tenant_folder,
                'region': region_folder,
                'url': presigned_url,
                'last_updated': last_updated.replace(microsecond=0).isoformat()
            }
            result.append(item)
        return result

    @staticmethod
    def get_monthly_price_dif(cur_hour_price, new_hour_price):
        if not isinstance(cur_hour_price, float) or \
                not isinstance(new_hour_price, float):
            return 0.0
        cur_price_month = cur_hour_price * HOURS_IN_MONTH
        new_hour_price = new_hour_price * HOURS_IN_MONTH
        return round(cur_price_month - new_hour_price, 2)

    @staticmethod
    def get_monthly_price(hour_price):
        if not isinstance(hour_price, (int, float)):
            return 0.0
        return round(hour_price * HOURS_IN_MONTH, 2)

    @staticmethod
    def get_readable_schedule(schedule_item):
        start_time = schedule_item.get('start')
        stop_time = schedule_item.get('stop')

        time_part = f'{start_time} - {stop_time}'
        weekdays = schedule_item.get('weekdays')

        if not start_time or not stop_time or not weekdays:
            return
        days_part = []
        if len(weekdays) == 1:
            days_part.append(weekdays[0])
        else:
            days_part.append(weekdays[0])
            days_part.append(weekdays[-1])

        days_part = ' - '.join(days_part)
        return ', '.join((time_part, days_part))

    def get_storage(self, customer: str):
        application = self.application_service.get_host_application(
            customer=customer)

        if not application:
            _LOG.error(f'Host Application for customer \'{customer}\' '
                       f'does not found.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Host Application for customer \'{customer}\' '
                        f'does not found.'
            )
        application_meta = self.application_service.get_application_meta(
            application=application)

        output_storage = application_meta.output_storage

        if not output_storage:
            _LOG.error(f'Output storage is not specified in application '
                       f'\'{application.application_id}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Output storage is not specified in application '
                        f'\'{application.application_id}\''
            )

        storage = self.storage_service.get_by_name(name=output_storage)
        if not storage:
            _LOG.error(f'Storage \'{output_storage}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Storage \'{output_storage}\' does not exist.'
            )
        return storage
