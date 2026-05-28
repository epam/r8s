from enum import Enum

from commons import raise_error_response, secure_event
from commons.abstract_lambda import ACTION_PARAM
from commons.constants import GET_METHOD
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.algorithm_processor import \
    AlgorithmProcessor
from lambdas.r8s_api_handler.processors.application_licenses_processor import \
    ApplicationLicensesProcessor
from lambdas.r8s_api_handler.processors.application_processor import \
    ApplicationProcessor
from lambdas.r8s_api_handler.processors.dojo_application_processor import \
    DojoApplicationProcessor
from lambdas.r8s_api_handler.processors.dojo_parent_processor import \
    DojoParentProcessor
from lambdas.r8s_api_handler.processors.health_check_processor import \
    HealthCheckProcessor
from lambdas.r8s_api_handler.processors.job_processor import JobProcessor
from lambdas.r8s_api_handler.processors.license_manager_client_processor import \
    LicenseManagerClientProcessor
from lambdas.r8s_api_handler.processors.license_manager_config_processor import \
    LicenseManagerConfigProcessor
from lambdas.r8s_api_handler.processors.license_sync_processor import \
    LicenseSyncProcessor
from lambdas.r8s_api_handler.processors.mail_report_processor import \
    MailReportProcessor
from lambdas.r8s_api_handler.processors.parent_processor import ParentProcessor
from lambdas.r8s_api_handler.processors.parent_resize_insights_processor import \
    ParentResizeInsightsProcessor
from lambdas.r8s_api_handler.processors.policies_processor import \
    PolicyProcessor
from lambdas.r8s_api_handler.processors.recommendation_history_processor import \
    RecommendationHistoryProcessor
from lambdas.r8s_api_handler.processors.refresh_processor import \
    RefreshProcessor
from lambdas.r8s_api_handler.processors.report_processor import ReportProcessor
from lambdas.r8s_api_handler.processors.resource_group_processor import \
    ResourceGroupProcessor
from lambdas.r8s_api_handler.processors.role_processor import RoleProcessor
from lambdas.r8s_api_handler.processors.shape_price_processor import \
    ShapePriceProcessor
from lambdas.r8s_api_handler.processors.shape_price_sync_processor import \
    ShapePriceSyncProcessor
from lambdas.r8s_api_handler.processors.shape_processor import ShapeProcessor
from lambdas.r8s_api_handler.processors.shape_rule_dry_run_processor import \
    ShapeRuleDryRunProcessor
from lambdas.r8s_api_handler.processors.shape_rule_processor import \
    ShapeRuleProcessor
from lambdas.r8s_api_handler.processors.signin_processor import SignInProcessor
from lambdas.r8s_api_handler.processors.signup_processor import SignUpProcessor
from lambdas.r8s_api_handler.processors.storage_data_processor import \
    StorageDataProcessor
from lambdas.r8s_api_handler.processors.storage_processor import \
    StorageProcessor
from lambdas.r8s_api_handler.processors.user_processor import UserProcessor
from services.abstract_api_handler_lambda import AbstractApiHandlerLambda

_LOG = get_logger('R8sApiHandler-handler')


class Action(str, Enum):
    SIGNIN = 'signin'
    SIGNUP = 'signup'
    REFRESH = 'refresh'
    POLICY = 'policy'
    ROLE = 'role'
    ALGORITHM = 'algorithm'
    STORAGE = 'storage'
    APPLICATION = 'application'
    APPLICATION_LICENSES = 'application_licenses'
    APPLICATION_DOJO = 'application_dojo'
    JOB = 'job'
    REPORT = 'report'
    MAIL_REPORT = 'mail_report'
    STORAGE_DATA = 'storage_data'
    SHAPE_RULE = 'shape_rule'
    SHAPE_RULE_DRY_RUN = 'shape_rule_dry_run'
    RESOURCE_GROUP = 'resource_group'
    PARENT = 'parent'
    PARENT_DOJO = 'parent_dojo'
    PARENT_INSIGHTS_RESIZE = 'parent_insights_resize'
    SHAPE = 'shape'
    SHAPE_PRICE = 'shape_price'
    SHAPE_PRICE_SYNC = 'shape_price_sync'
    USER = 'user'
    HEALTH_CHECK = 'health_check'
    RECOMMENDATION = 'recommendation'
    LM_SETTING_CONFIG = 'settings-config'
    LM_SETTING_CLIENT = 'settings-client'
    LICENSE_SYNC = 'license-sync'


PROCESSOR_REGISTRY = {
    Action.SIGNIN: SignInProcessor.build,
    Action.SIGNUP: SignUpProcessor.build,
    Action.REFRESH: RefreshProcessor.build,
    Action.POLICY: PolicyProcessor.build,
    Action.ROLE: RoleProcessor.build,
    Action.ALGORITHM: AlgorithmProcessor.build,
    Action.STORAGE: StorageProcessor.build,
    Action.APPLICATION: ApplicationProcessor.build,
    Action.APPLICATION_LICENSES: ApplicationLicensesProcessor.build,
    Action.APPLICATION_DOJO: DojoApplicationProcessor.build,
    Action.JOB: JobProcessor.build,
    Action.REPORT: ReportProcessor.build,
    Action.MAIL_REPORT: MailReportProcessor.build,
    Action.STORAGE_DATA: StorageDataProcessor.build,
    Action.SHAPE_RULE: ShapeRuleProcessor.build,
    Action.SHAPE_RULE_DRY_RUN: ShapeRuleDryRunProcessor.build,
    Action.RESOURCE_GROUP: ResourceGroupProcessor.build,
    Action.PARENT: ParentProcessor.build,
    Action.PARENT_DOJO: DojoParentProcessor.build,
    Action.PARENT_INSIGHTS_RESIZE: ParentResizeInsightsProcessor.build,
    Action.SHAPE: ShapeProcessor.build,
    Action.SHAPE_PRICE: ShapePriceProcessor.build,
    Action.SHAPE_PRICE_SYNC: ShapePriceSyncProcessor.build,
    Action.USER: UserProcessor.build,
    Action.HEALTH_CHECK: HealthCheckProcessor.build,
    Action.RECOMMENDATION: RecommendationHistoryProcessor.build,
    Action.LM_SETTING_CONFIG: LicenseManagerConfigProcessor.build,
    Action.LM_SETTING_CLIENT: LicenseManagerClientProcessor.build,
    Action.LICENSE_SYNC: LicenseSyncProcessor.build,
}


class R8sApiHandler(AbstractApiHandlerLambda):
    def validate_request(self, event) -> dict:
        pass

    def handle_request(self, event, context):
        action_name = event.pop(ACTION_PARAM)
        if 'body' in event:
            if event.get('http_method') == GET_METHOD:
                body = event.pop('query', {}).get('querystring', {})
                event.pop('body', None)
            else:
                body = event.pop('body', {})
                event.pop('query', None)
            event.update(body)
        _LOG.debug(f'Formatted event: {secure_event(event=event)}')
        try:
            action = Action(action_name)
        except ValueError:
            action = None
        processor_builder = PROCESSOR_REGISTRY.get(action)
        if not processor_builder:
            error_message = f'There is no handler for action {action_name}'
            _LOG.info(f'request handle error: {error_message}')
            raise_error_response(content=error_message, code=400)
        return processor_builder().handle_command(event=event)


HANDLER = R8sApiHandler()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
