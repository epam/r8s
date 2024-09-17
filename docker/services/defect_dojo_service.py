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
from models.recommendation_history import RecommendationHistory
from services.clients.dojo_client import DojoV2Client
from services.ssm_service import SSMService

_LOG = get_logger('defect-dojo-service')


class DefectDojoService:
    def __init__(self, ssm_service: SSMService,
                 application: Application):
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
            json_data = self._jsonify_history_item(item)
            base64_encoded = (base64.b64encode(json_data.encode('utf-8'))
                              .decode('utf-8'))
            finding = {
                'title': f"{item.resource_id}",
                'description': f"{item.recommendation_type.value} "
                               f"recommendation for \'{item.resource_id}\' "
                               f"instance.",
                'severity': "Info",
                'date': item.added_at.isoformat(),
                'files': [
                    {
                        'title': "recommendation.json",
                        'data': base64_encoded
                    }
                ]
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
        if isinstance(secret_value, dict):
            secret_value = secret_value.get('api_key')
        return secret_value

    @staticmethod
    def _jsonify_history_item(recommendation: RecommendationHistory):
        item_dict = recommendation.get_json()

        item_dict.pop('_id')
        dt_attrs = ['added_at', 'feedback_dt', 'last_metric_capture_date']

        for attr_name in dt_attrs:
            attr_value = item_dict.get(attr_name)
            if attr_value and isinstance(attr_value, datetime.datetime):
                item_dict[attr_name] = item_dict[attr_name].isoformat()
        return json.dumps(item_dict)
