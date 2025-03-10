import itertools
import json
import math
from datetime import datetime, timedelta
from typing import List, Union
from uuid import uuid4

from modular_sdk.commons import ModularException
from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.impl.maestro_rabbit_transport_service \
    import MaestroRabbitMQTransport
from modular_sdk.services.tenant_service import TenantService

from commons import build_response, RESPONSE_BAD_REQUEST_CODE, \
    RESPONSE_INTERNAL_SERVER_ERROR, RESPONSE_OK_CODE
from commons.constants import CUSTOMER_ATTR, TENANT_ATTR, \
    RECOMMENDATION_SETTINGS_ATTR, TARGET_TIMEZONE_NAME_ATTR, TENANTS_ATTR, \
    RECOMMENDATION_TYPE_ATTR
from commons.log_helper import get_logger
from models.recommendation_history import RecommendationHistory, \
    RecommendationTypeEnum
from services import SERVICE_PROVIDER
from services.abstract_lambda import AbstractLambda
from services.algorithm_service import AlgorithmService
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.recommendation_history_service import \
    RecommendationHistoryService
from services.rightsizer_application_service import \
    RightSizerApplicationService

_LOG = get_logger('r8s-report-generator')

MAX_PRIORITY_RESOURCES = 10
MAX_RESOURCES_PER_TYPE = 10

COMMAND_NAME = 'SEND_MAIL'

TENANT_REPORT_TYPE = 'RIGHTSIZER_TENANT_REPORT'
UTC_TIMEZONE_NAME = 'Etc/UTC'


class ReportGenerator(AbstractLambda):

    def __init__(self, job_service: JobService,
                 tenant_service: TenantService,
                 customer_service: CustomerService,
                 recommendation_service: RecommendationHistoryService,
                 maestro_rabbitmq_service: MaestroRabbitMQTransport,
                 application_service: RightSizerApplicationService,
                 algorithm_service: AlgorithmService,
                 environment_service: EnvironmentService):
        self.job_service = job_service
        self.tenant_service = tenant_service
        self.customer_service = customer_service
        self.recommendation_service = recommendation_service
        self.maestro_rabbitmq_service = maestro_rabbitmq_service
        self.application_service = application_service
        self.algorithm_service = algorithm_service
        self.environment_service = environment_service

    def validate_request(self, event):
        pass

    def handle_request(self, event, context):
        customer_name = event.get(CUSTOMER_ATTR)
        tenants = event.get(TENANTS_ATTR)

        customer = self.customer_service.get(name=customer_name)

        if not customer:
            _LOG.error(f'Customer \'{customer_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Customer \'{customer_name}\' does not exist.'
            )
        if not tenants:
            _LOG.debug(f'\'{TENANTS_ATTR}\' attribute must be specified.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{TENANTS_ATTR}\' attribute must be specified.'
            )
        response = {}
        for tenant_name in tenants:
            try:
                tenant = self.tenant_service.get(tenant_name=tenant_name)
                if not tenant:
                    _LOG.error(f'Tenant \'{tenant_name}\' does not exist.')
                    return build_response(
                        code=RESPONSE_BAD_REQUEST_CODE,
                        content=f'Tenant \'{tenant_name}\' does not exist.'
                    )

                processing_days = self.environment_service. \
                    mail_report_process_days()

                priority_saving_threshold = self.environment_service. \
                    mail_report_high_priority_threshold()
                _LOG.debug(f'Generating report for \'{customer_name}\' tenant '
                           f'\'{tenant_name}\'. Processing days: '
                           f'{processing_days}, high priority saving '
                           f'threshold: {priority_saving_threshold}')
                report = self.generate_report(
                    customer=customer, tenant=tenant,
                    processing_days=processing_days,
                    priority_saving_threshold= \
                        priority_saving_threshold)

                _LOG.debug('Preparing request for sending to maestro')
                formatted_report = self.prepare_request(report=report)

                _LOG.debug('Formatted report: {formatted_report}')
                _LOG.debug('Sending request to Maestro')

                response_code, response_message = \
                    self._send_notification_to_m3(json_model=formatted_report)
                _LOG.debug(f'Response: {response_message}')
                response[tenant_name] = response_message
            except Exception as e:
                message = f'Exception occurred while sending report for ' \
                          f'tenant: \'{tenant_name}\': {e}'
                _LOG.error(message)
                response[tenant_name] = message

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def generate_report(self, customer, tenant, processing_days,
                        priority_saving_threshold):
        processing_from_date, processing_to_date = \
            self.get_processing_date_range(processing_days)

        recommendations = self.recommendation_service.list(
            customer=customer.name,
            tenant=tenant.name,
            from_dt=processing_from_date
        )
        if not recommendations:
            _LOG.error(f'No recommendations found '
                       f'for tenant \'{tenant.name}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No recommendations found '
                        f'for tenant \'{tenant.name}\''
            )

        _LOG.debug(f'Filtering only recommendations with available savings.')
        recommendations = [i for i in recommendations if i.savings]

        _LOG.debug('Filtering recommendation to include only one '
                   'recommendations from the last job with the resource')
        recommendations = self.filter_latest_job_resource(
            recommendations=recommendations
        )

        _LOG.debug('Formatting recommendations')
        formatted = []
        for recommendation in recommendations:
            formatted_recommendation = self.format_recommendation(
                recommendation=recommendation)
            if formatted_recommendation:
                formatted.append(formatted_recommendation)

        priority_resources = self.get_priority(
            formatted_recommendations=formatted,
            saving_threshold=priority_saving_threshold)

        _LOG.debug('Calculating total summary')
        total_summary = self._resources_summary(resources=formatted)
        _LOG.debug('Total summary: {total_summary}')
        if len(priority_resources) > MAX_PRIORITY_RESOURCES:
            priority_resources = priority_resources[0:MAX_PRIORITY_RESOURCES]

        _LOG.debug('Dividing resources by recommendation type')
        by_type = self.divide_by_recommendation_type(
            formatted,
            max_per_type=MAX_RESOURCES_PER_TYPE)

        _LOG.debug('Calculating displayed items summary')
        displayed_resources = list(itertools.chain.from_iterable(
            by_type.values()))
        report_summary = self._resources_summary(
            resources=list(displayed_resources))
        _LOG.debug(f'Displayed resources summary: {report_summary}')

        job_id = self.get_most_frequent_job_id(recommendations=recommendations)

        report_item = {
            'summary': {
                "total": total_summary,
                "displayed": report_summary
            },
            'high_priority': priority_resources,
            'detailed': by_type,
            "from": self.to_milliseconds(processing_from_date),
            "to": self.to_milliseconds(processing_to_date),
            CUSTOMER_ATTR: customer.name,
            TENANT_ATTR: tenant.name,
            "timezone": self.resolve_timezone(job_id=job_id)
        }
        _LOG.debug(f'Report: {report_item}')
        return report_item

    def _send_notification_to_m3(self, json_model: Union[list, dict]):
        try:
            code, status, response = self.maestro_rabbitmq_service.send_sync(
                command_name=COMMAND_NAME,
                parameters=json_model,
                is_flat_request=False, async_request=False,
                secure_parameters=None, compressed=True)
            _LOG.debug(f'Response code: {code}, response message: {response}')
            return code, response
        except ModularException as e:
            _LOG.error(f'Modular error: {e}')
            return build_response(
                code=RESPONSE_INTERNAL_SERVER_ERROR,
                content='An error occurred while sending the report.'
                        'Please contact the support team.'
            )

    @staticmethod
    def to_milliseconds(dt: datetime):
        return int(dt.timestamp()) * 1000

    @staticmethod
    def get_most_frequent_job_id(recommendations: List[RecommendationHistory]):
        job_ids = [recommendation.job_id for recommendation
                   in recommendations if recommendation.job_id]
        return max(set(job_ids), key=job_ids.count)

    @staticmethod
    def prepare_request(report: dict):
        return [
            {
                'viewType': 'm3',
                'model': {
                    "uuid": str(uuid4()),
                    "notificationType": TENANT_REPORT_TYPE,
                    "notificationAsJson": json.dumps(
                        {**report,
                         'report_type': TENANT_REPORT_TYPE},
                        separators=(",", ":")),
                    "notificationProcessorTypes": ["MAIL"]
                }
            }
        ]

    @staticmethod
    def get_processing_date_range(processing_days):
        stop = datetime.now()
        start = stop - timedelta(days=processing_days)
        return start, stop

    @staticmethod
    def filter_latest_job_resource(
            recommendations: List[RecommendationHistory]):
        recommendations = sorted(list(recommendations),
                                 key=lambda i: i['added_at'],
                                 reverse=True)
        resource_mapping = {}
        result = []
        resource_job_id_mapping = {}
        for recommendation in recommendations:
            instance_id = recommendation.resource_id
            recommendation_type = recommendation.get_json().get(
                RECOMMENDATION_TYPE_ATTR)

            if not recommendation.current_month_price_usd \
                    or not recommendation.savings \
                    or not recommendation.current_instance_type:
                continue

            if instance_id not in resource_mapping:
                resource_job_id_mapping[instance_id] = recommendation.job_id
                resource_mapping[instance_id] = {}
            if recommendation_type not in resource_mapping[instance_id] \
                    and recommendation.job_id == resource_job_id_mapping.get(
                instance_id):
                resource_mapping[instance_id][recommendation_type] = \
                    recommendation
                result.append(recommendation)
        return result

    def get_priority(self, formatted_recommendations: list,
                     saving_threshold: int):
        resource_mapping = {}

        for recommendation in formatted_recommendations:
            resource_id = recommendation.get('resource_id')
            recommendation_type = recommendation.get('recommendation_type')
            if resource_id not in resource_mapping:
                resource_mapping[resource_id] = {}
            if recommendation_type not in resource_mapping[resource_id]:
                resource_mapping[resource_id][
                    recommendation_type] = recommendation

        for recommendation in resource_mapping.values():
            recommendation['estimated_savings'] = \
                self._get_resource_saving(recommendation)

        if saving_threshold and saving_threshold > 0:
            _LOG.debug(f'Filtering priority resources with saving gt '
                       f'{saving_threshold}')
            resource_mapping = {k: v for k, v in resource_mapping.items()
                                if max(v.get('estimated_savings')) >
                                saving_threshold}
        _LOG.debug(f'Sorting priority resources by savings')
        priority_resources = sorted(resource_mapping.values(),
                                    key=lambda m: max(
                                        m.get('estimated_savings')),
                                    reverse=True)

        result = []

        for resource in priority_resources:
            recommendation_keys = [key for key in resource.keys() if
                                   key.isupper()]
            recommendation = resource[recommendation_keys[0]]
            current_price = recommendation.get('current_price')

            item = {
                'resource_id': recommendation.get('resource_id'),
                'current_price': current_price,
                'current_instance_type': recommendation.get(
                    'current_instance_type'),
                "region": recommendation.get('region'),
                'estimated_saving': resource.get('estimated_savings'),
                'recommendations': {}
            }
            for key in recommendation_keys:
                recommendation = resource[key]
                item['recommendations'][key] = {
                    "recommendation": recommendation.get('recommendation'),
                    "estimated_saving": recommendation.get('estimated_saving')
                }

            result.append(item)
        return result

    def _get_resource_saving(self, resource: dict):
        saving_percent_options = []

        min_saving_percent = self._get_min_saving_percent(resource=resource)
        saving_percent_options.append(min_saving_percent)

        max_saving_percent = self._get_max_saving_percent(resource=resource)
        saving_percent_options.append(max_saving_percent)

        saving_percent_options = sorted(list(set(saving_percent_options)))

        recommendation_key = [key for key in resource.keys() if key.isupper()][
            0]
        month_price = resource[recommendation_key]['current_price']

        return [round(month_price * percent / 100, 2)
                for percent in saving_percent_options]

    def _get_min_saving_percent(self, resource):
        min_percents = []

        for recommendation_type, recommendation in resource.items():
            saving_percent = recommendation.get('saving_percent')
            if isinstance(saving_percent, int):
                min_percents.append(saving_percent)
            else:
                min_percents.append(min(saving_percent))

        while len(min_percents) > 1 and max(min_percents) > 0:
            min_percents.remove(max(min_percents))

        return self.get_saving_percent(option_saving_percents=min_percents)

    def _get_max_saving_percent(self, resource):
        max_percents = []

        for recommendation_type, recommendation in resource.items():
            saving_percent = recommendation.get('saving_percent')
            if isinstance(saving_percent, int):
                max_percents.append(saving_percent)
            else:
                max_percents.append(max(saving_percent))

        while len(max_percents) > 1 and min(max_percents) < 0:
            max_percents.remove(min(max_percents))

        return self.get_saving_percent(option_saving_percents=max_percents)

    @staticmethod
    def get_saving_percent(option_saving_percents):
        if len(option_saving_percents) == 1:
            return option_saving_percents[0]
        option_saving_percents = [1 - round(item / 100, 2)
                                  for item in option_saving_percents]
        return (1 - math.prod(option_saving_percents)) * 100

    @staticmethod
    def divide_by_recommendation_type(recommendations: list, max_per_type):
        result = {}
        for recommendation in recommendations:
            recommendation_type = recommendation.get('recommendation_type')
            if recommendation_type not in result:
                result[recommendation_type] = []
            result[recommendation_type].append(recommendation)

        for recommendation_type in result.keys():
            result[recommendation_type] = sorted(
                result[recommendation_type],
                key=lambda r: max(r.get('estimated_saving')),
                reverse=True
            )
            if len(result[recommendation_type]) > max_per_type:
                type_result = result[recommendation_type][0:max_per_type]
                result[recommendation_type] = type_result
        return result

    def format_recommendation(self, recommendation: RecommendationHistory):
        recommendation_type = recommendation.get_json().get(
            RECOMMENDATION_TYPE_ATTR)

        resize_actions = [i.value for i in RecommendationTypeEnum.resize()]
        if recommendation_type == RecommendationTypeEnum.ACTION_SHUTDOWN.value:
            return self._format_shutdown_recommendation(
                recommendation=recommendation)
        elif recommendation_type == RecommendationTypeEnum.ACTION_SCHEDULE.value:
            return self._format_schedule_recommendation(
                recommendation=recommendation)
        elif recommendation_type in resize_actions:
            return self._format_resize_recommendation(
                recommendation=recommendation)

    @staticmethod
    def _format_resize_recommendation(recommendation):
        recommended_instances = [dict(item) for
                                 item in recommendation.recommendation]

        savings = reversed(recommendation.savings)

        estimated_savings = []
        for saving in savings:
            if isinstance(saving, dict):
                estimated_savings.append(saving['saving_month_usd'])
            else:
                estimated_savings.append(saving)

        if len(estimated_savings) > 2:
            estimated_savings = [estimated_savings[0], estimated_savings[-1]]
        saving_percents = [
            round(saving_item / recommendation.current_month_price_usd,
                  2) * 100
            for saving_item in estimated_savings]
        result = {
            "resource_id": recommendation.resource_id,
            "recommendation": recommended_instances,
            "recommendation_type": recommendation.recommendation_type.value,
            "description": "",
            "current_price": recommendation.current_month_price_usd,
            "current_instance_type": recommendation.current_instance_type,
            "region": recommendation.region,
            "estimated_saving": estimated_savings,
            "saving_percent": sorted(saving_percents)
        }
        if recommendation.recommendation_type == \
                RecommendationTypeEnum.ACTION_SPLIT:
            shape_koefs = [item.get('probability')
                           for item in recommendation.recommendation
                           if item.get('probability')]
            result['probability'] = shape_koefs
        return result

    @staticmethod
    def _format_schedule_recommendation(recommendation):
        savings_usd = []
        for saving in recommendation.savings:
            if isinstance(saving, dict):
                savings_usd.append(saving['saving_month_usd'])
            else:
                savings_usd.append(saving)
        saving_percents = [
            round(saving_item / recommendation.current_month_price_usd,
                  2) * 100
            for saving_item in savings_usd]
        return {
            "resource_id": recommendation.resource_id,
            "recommendation": list(recommendation.recommendation),
            "recommendation_type": recommendation.recommendation_type.value,
            "description": "",
            "current_price": recommendation.current_month_price_usd,
            "current_instance_type": recommendation.current_instance_type,
            "region": recommendation.region,
            "estimated_saving": sorted(savings_usd),
            "saving_percent": sorted(saving_percents)
        }

    @staticmethod
    def _format_shutdown_recommendation(recommendation):
        savings_usd = []
        for saving in recommendation.savings:
            if isinstance(saving, dict):
                savings_usd.append(saving['saving_month_usd'])
            else:
                savings_usd.append(saving)
        return {
            "resource_id": recommendation.resource_id,
            "recommendation": [],
            "recommendation_type": recommendation.recommendation_type.value,
            "description": "",
            "current_price": recommendation.current_month_price_usd,
            "current_instance_type": recommendation.current_instance_type,
            "region": recommendation.region,
            "estimated_saving": sorted(savings_usd),
            "saving_percent": [100]
        }

    @staticmethod
    def _resources_summary(resources: list):
        used_resource_ids = []
        result_saving = [0, 0]
        total_cost = 0

        for resource in resources:
            resource_id = resource.get('resource_id')
            if resource_id in used_resource_ids:
                continue
            resource_price = resource.get('current_price')
            total_cost += resource_price

            resource_saving = resource.get('estimated_saving')
            if len(resource_saving) == 1:
                if resource_saving[0] < 0:
                    result_saving[0] += resource_saving[0]
                else:
                    result_saving[1] += resource_saving[0]
            elif len(resource_saving) == 2:
                if resource_saving[0] < 0:
                    result_saving[0] += resource_saving[0]
                if resource_saving[1] > 0:
                    result_saving[1] += resource_saving[1]
            used_resource_ids.append(resource_id)

        result_saving = [round(item, 2) for item in result_saving]

        return {
            "resource_count": len(used_resource_ids),
            "current_estimated_cost": round(total_cost, 2),
            "estimated_saving": result_saving
        }

    def resolve_timezone(self, job_id):
        job = self.job_service.get_by_id(job_id)

        if not job:
            _LOG.error(f'No job with id \'{job_id}\' found')
            return UTC_TIMEZONE_NAME
        application_id = job.application_id
        if not application_id:
            _LOG.error(f'Job \'{job_id}\' does not have application_id specified.')
            return UTC_TIMEZONE_NAME
        application = self.application_service.get_application_by_id(
            application_id=application_id)
        if not application:
            _LOG.error(f'Application with id \'{application_id}\' '
                       f'does not exist.')
            return UTC_TIMEZONE_NAME
        app_meta = self.application_service.get_application_meta(
            application=application)
        if not app_meta:
            _LOG.error(f'Application \'{application_id}\' meta is empty.')
            return UTC_TIMEZONE_NAME

        algorithm_name = app_meta.as_dict().get('algorithm_map', {}).get('VM')
        if not algorithm_name:
            _LOG.error(f'No VM algorithm specified in application '
                       f'\'{application_id}\'.')
            return UTC_TIMEZONE_NAME
        algorithm = self.algorithm_service.get_by_name(name=algorithm_name)
        if not algorithm:
            _LOG.error(f'Algorithm \'{algorithm_name}\' does not exist.')
            return UTC_TIMEZONE_NAME
        recommendation_settings = algorithm.get_json().get(
            RECOMMENDATION_SETTINGS_ATTR, {})
        target_timezone_name = recommendation_settings.get(
            TARGET_TIMEZONE_NAME_ATTR, UTC_TIMEZONE_NAME)
        _LOG.debug(f'Resolved timezone: {target_timezone_name}')
        return target_timezone_name


HANDLER = ReportGenerator(
    job_service=SERVICE_PROVIDER.job_service(),
    customer_service=SERVICE_PROVIDER.customer_service(),
    tenant_service=SERVICE_PROVIDER.tenant_service(),
    recommendation_service=SERVICE_PROVIDER.recommendation_history_service(),
    maestro_rabbitmq_service=SERVICE_PROVIDER.maestro_rabbitmq_service(),
    application_service=SERVICE_PROVIDER.rightsizer_application_service(),
    algorithm_service=SERVICE_PROVIDER.algorithm_service(),
    environment_service=SERVICE_PROVIDER.environment_service())


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
