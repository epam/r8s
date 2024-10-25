import base64
import datetime
import json

from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent
from modular_sdk.commons.constants import ApplicationType, ParentType
from commons.log_helper import get_logger
from commons.constants import JOB_STEP_GENERATE_REPORTS
from commons.exception import ExecutorException
from modular_sdk.services.impl.maestro_credentials_service import (
    DefectDojoApplicationMeta
)

from models.parent_attributes import DojoParentMeta
from models.recommendation_history import RecommendationHistory, \
    RecommendationTypeEnum
from services.clients.dojo_client import DojoV2Client
from services.ssm_service import SSMService

_LOG = get_logger('defect-dojo-service')


class RecommendationToTextConverter:
    SHUTDOWN_TEMPLATE = ("Shutting down is suggested for the instances with "
                         "minimum load, which allows to suppose that the "
                         "instance is not actually used. \nIt is recommended to "
                         "carefully review the instance purpose and "
                         "role within the infrastructure before the shutdown.")
    SPLIT_TEMPLATE = (
        "Your instance utilisation is not homogenous. You can optimise "
        "it by splitting the instance into several ones, so that each "
        "one would fit the specific load."
    )
    SPLIT_ITEM_TEMPLATE = (
        "- The {instance_type} fits {coverage}% of analyzed time period."
    )
    SCALE_UP_TEMPLATE = (
        "Scaling up allows to increase instance capacity by selecting a "
        "new shape with larger CPU and RAM."
        "\nThis allows to adjust the instance configuration to its real "
        "workload and get maximum value for the reasonable price."
        "\nRecommended shapes: {instance_types}"
    )
    SCALE_DOWN_TEMPLATE = (
        "Scaling down allows to decrease instance capacity by selecting a "
        "new shape with smaller CPU and RAM."
        "\nThis allows to adjust the instance configuration to its real "
        "workload and get maximum value for the reasonable price."
        "\nRecommended shapes: {instance_types}"
    )
    RESIZE_TEMPLATE = (
        "Changing instance shape allows to adjust the instance capacity "
        "to its actual load and purpose."
        "\nRecommended shapes: {instance_types}"
    )
    SCHEDULE_TEMPLATE = (
        "Your instance load has a rhythmic pattern that allows to set up "
        "start/stop schedules to cut its costs."
        "\nThe following runtime schedules are suggested:\n"
    )
    SCHEDULE_ITEM_TEMPLATE = (
        "{weekdays}: [start - {time_start}, "
        "stop - {time_stop}]"
    )

    @property
    def type_converter_mapping(self):
        return {
            RecommendationTypeEnum.ACTION_SHUTDOWN.value:
                self._convert_shutdown,
            RecommendationTypeEnum.ACTION_SCHEDULE.value:
                self._convert_schedule,
            RecommendationTypeEnum.ACTION_SPLIT.value:
                self._convert_split,
            RecommendationTypeEnum.ACTION_SCALE_DOWN.value:
                self._convert_scale_down,
            RecommendationTypeEnum.ACTION_SCALE_UP.value:
                self._convert_scale_up,
            RecommendationTypeEnum.ACTION_CHANGE_SHAPE.value:
                self._convert_resize
        }

    def convert(self, recommendation: RecommendationHistory):
        recommendation_type = recommendation.recommendation_type.value
        converter = self.type_converter_mapping.get(recommendation_type)

        common_prefix = (f"{recommendation.recommendation_type.value} "
                         f"recommendation for "
                         f"\'{recommendation.resource_id}\' instance.")
        readable_part = None
        if converter:
            readable_part: str | None = converter(recommendation)

        raw_part = self._jsonify_history_item(recommendation)

        description_parts = [common_prefix, readable_part, raw_part]
        description_parts = [i for i in description_parts if i]
        result = '\n\n'.join(description_parts)
        if not result:
            result = ''
        return result

    def _convert_shutdown(self, item: RecommendationHistory) -> str:
        return self.SHUTDOWN_TEMPLATE

    def _convert_scale_down(self, item: RecommendationHistory) -> str:
        instance_types = [i.get('name') for i in item.recommendation]
        instance_types = ', '.join(instance_types)
        return self.SCALE_DOWN_TEMPLATE.format(instance_types=instance_types)

    def _convert_scale_up(self, item: RecommendationHistory) -> str:
        instance_types = [i.get('name') for i in item.recommendation]
        instance_types = ', '.join(instance_types)
        return self.SCALE_UP_TEMPLATE.format(instance_types=instance_types)

    def _convert_resize(self, item: RecommendationHistory) -> str:
        instance_types = [i.get('name') for i in item.recommendation]
        instance_types = ', '.join(instance_types)
        return self.RESIZE_TEMPLATE.format(instance_types=instance_types)

    def _convert_schedule(self, item: RecommendationHistory) -> str | None:
        schedules = list(item.recommendation)
        if not schedules:
            return

        parts = [self.SCHEDULE_TEMPLATE]

        for schedule_item_data in schedules:
            weekday_start = schedule_item_data.get('weekdays')[0]
            weekday_stop = schedule_item_data.get('weekdays')[-1]
            start = schedule_item_data.get('start')
            stop = schedule_item_data.get('stop')

            if not weekday_start or not weekday_stop or not start or not stop:
                continue
            if weekday_start == weekday_stop:
                weekdays = weekday_start
            else:
                weekdays = f'{weekday_start} - {weekday_stop}'
            part = self.SCHEDULE_ITEM_TEMPLATE.format(
                weekdays=weekdays,
                time_start=start,
                time_stop=stop
            )
            parts.append(part)

        if len(parts) > 1:
            return '\n'.join(parts)
        return

    def _convert_split(self, item: RecommendationHistory) -> str:
        recommended_instances = list(item.recommendation)
        parts = [self.SPLIT_TEMPLATE]

        for instance_data in recommended_instances:
            instance_name = instance_data.get('name')
            coverage = instance_data.get('probability', 0)
            coverage_percent = int(coverage * 100)
            if instance_name and coverage_percent is not None \
                    and 0 < coverage_percent <= 100:
                part_item = self.SPLIT_ITEM_TEMPLATE.format(
                    instance_type=instance_name,
                    coverage=coverage_percent
                )
                parts.append(part_item)

        if len(parts) > 1:
            return '\n'.join(parts)
        return self.SPLIT_TEMPLATE

    @staticmethod
    def _jsonify_history_item(recommendation: RecommendationHistory):
        item_dict = recommendation.get_json()

        item_dict.pop('_id')
        dt_attrs = ['added_at', 'feedback_dt', 'last_metric_capture_date']

        for attr_name in dt_attrs:
            attr_value = item_dict.get(attr_name)
            if attr_value and isinstance(attr_value, datetime.datetime):
                item_dict[attr_name] = item_dict[attr_name].isoformat()
        return json.dumps(item_dict, indent=4)


class DefectDojoService:
    def __init__(self, ssm_service: SSMService,
                 application: Application):
        _LOG.debug(f'Initializing DefectDojo service')
        self.ssm_service = ssm_service

        if not application.type == ApplicationType.DEFECT_DOJO.value:
            _LOG.error(
                f'Error occurred during DefectDojo initialization: Application '
                f'with type \'{ApplicationType.DEFECT_DOJO.value}\' '
                f'expected, got {application.type}. '
                f'Application id \'{application.application_id}\'')
            raise ExecutorException(
                step_name=JOB_STEP_GENERATE_REPORTS,
                reason=f'Error occurred during DefectDojo '
                       f'initialization: Application '
                       f'with type \'{ApplicationType.DEFECT_DOJO.value}\' '
                       f'expected, got {application.type}. '
                       f'Application id \'{application.application_id}\''
            )
        app_meta = application.meta.as_dict()
        self._meta = DefectDojoApplicationMeta.from_dict(app_meta)
        self._api_key = self._get_api_key(application=application)
        self.client = DojoV2Client(
            url=self._meta.url,
            api_key=self._api_key
        )

    def push_findings(
            self, parent: Parent,
            recommendation_history_items: list[RecommendationHistory]
    ):
        _LOG.debug(f'Going to push {len(recommendation_history_items)} '
                   f'findings to DefectDojo'
                   f' for parent: {parent.parent_id}')
        if not parent.type == ParentType.RIGHTSIZER_SIEM_DEFECT_DOJO.value:
            _LOG.error(
                f'Error occurred during DefectDojo initialization: Parent '
                f'with type \'{ParentType.RIGHTSIZER_SIEM_DEFECT_DOJO.value}\' '
                f'expected, got {parent.type}. '
                f'Parent id \'{parent.parent_id}\'')
            return
        _LOG.debug(f'Loading parent {parent.parent_id} meta')
        parent_meta = DojoParentMeta.from_parent(parent)

        _LOG.debug(f'Formatting recommendations for dojo')
        data = self._to_dojo_report(recommendation_history_items)
        tenant_name = recommendation_history_items[0].tenant
        job_id = recommendation_history_items[0].job_id

        _LOG.debug(f'Uploading {len(recommendation_history_items)} findings '
                   f'from tenant {tenant_name}. Job id: {job_id}')
        self.client.import_scan(
            scan_type=parent_meta.scan_type,
            scan_date=datetime.datetime.now(),
            product_type_name=parent_meta.product_type,
            product_name=parent_meta.product.format(tenant_name=tenant_name),
            engagement_name=parent_meta.engagement,
            test_title=parent_meta.test.format(job_id=job_id),
            data=data
        )

    def _to_dojo_report(
            self, recommendation_history_items: list[RecommendationHistory]
    ):
        findings = []

        for item in recommendation_history_items:
            converter = RecommendationToTextConverter()
            finding = {
                'title': f"{item.resource_id}",
                'description': converter.convert(item),
                'severity': "Info",
                'date': item.added_at.isoformat()
            }
            findings.append(finding)
        return {'findings': findings}

    def _get_api_key(self, application: Application):
        secret_name = application.secret
        secret_value = self.ssm_service.get_secret_value(
            secret_name=secret_name
        )
        if not secret_value:
            _LOG.error(f'Something went wrong trying to extract Defect Dojo '
                       f'api key from ssm. Application id: '
                       f'\'{application.application_id}\'')
            raise ExecutorException(
                step_name=JOB_STEP_GENERATE_REPORTS,
                reason=f'Something went wrong trying to extract Defect Dojo '
                       f'api key from ssm. Application id: '
                       f'\'{application.application_id}\''
            )
        if isinstance(secret_value, str):
            try:
                secret_value = json.loads(secret_value)
            except json.decoder.JSONDecodeError:
                pass
        if isinstance(secret_value, dict):
            secret_value = secret_value.get('api_key')
        return secret_value
