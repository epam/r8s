from modular_sdk.services.customer_service import CustomerService
from modular_sdk.services.tenant_service import TenantService

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
from lambdas.r8s_api_handler.processors.group_policy_processor import \
    GroupPolicyProcessor
from lambdas.r8s_api_handler.processors.health_check_processor import \
    HealthCheckProcessor
from lambdas.r8s_api_handler.processors.job_processor import JobProcessor
from lambdas.r8s_api_handler.processors.license_manager_client_processor import \
    LicenseManagerClientProcessor
from lambdas.r8s_api_handler.processors.license_manager_config_processor import \
    LicenseManagerConfigProcessor
from lambdas.r8s_api_handler.processors.license_processor import \
    LicenseProcessor
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
from lambdas.r8s_api_handler.processors.role_processor import RoleProcessor
from lambdas.r8s_api_handler.processors.shape_price_processor import \
    ShapePriceProcessor
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
from services import SERVICE_PROVIDER
from services.abstract_api_handler_lambda import AbstractApiHandlerLambda
from services.algorithm_service import AlgorithmService
from services.clients.api_gateway_client import ApiGatewayClient
from services.clients.batch import BatchClient
from services.clients.lambda_func import LambdaClient
from services.clients.s3 import S3Client
from services.customer_preferences_service import CustomerPreferencesService
from services.environment_service import EnvironmentService
from services.job_service import JobService
from services.key_management_service import KeyManagementService
from services.license_manager_service import LicenseManagerService
from services.license_service import LicenseService
from services.rbac.access_control_service import AccessControlService
from services.rbac.iam_service import IamService
from services.recommendation_history_service import \
    RecommendationHistoryService
from services.report_service import ReportService
from services.resize_service import ResizeService
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.setting_service import SettingsService
from services.shape_price_service import ShapePriceService
from services.shape_rule_filter_service import ShapeRulesFilterService
from services.shape_service import ShapeService
from services.ssm_service import SSMService
from services.storage_service import StorageService
from services.user_service import CognitoUserService

_LOG = get_logger('R8sApiHandler-handler')

SIGNIN_ACTION = 'signin'
SIGNUP_ACTION = 'signup'
REFRESH_ACTION = 'refresh'
POLICY_ACTION = 'policy'
ROLE_ACTION = 'role'
ALGORITHM_ACTION = 'algorithm'
STORAGE_ACTION = 'storage'
APPLICATION_ACTION = 'application'
APPLICATION_LICENSES_ACTION = 'application_licenses'
APPLICATION_DOJO_ACTION = 'application_dojo'
JOB_ACTION = 'job'
REPORT_ACTION = 'report'
MAIL_REPORT_ACTION = 'mail_report'
STORAGE_DATA_ACTION = 'storage_data'
SHAPE_RULE_ACTION = 'shape_rule'
SHAPE_RULE_DRY_RUN_ACTION = 'shape_rule_dry_run'
PARENT_ACTION = 'parent'
PARENT_DOJO_ACTION = 'parent_dojo'
PARENT_INSIGHTS_RESIZE_ACTION = 'parent_insights_resize'
SHAPE_ACTION = 'shape'
SHAPE_PRICE_ACTION = 'shape_price'
USER_ACTION = 'user'
HEALTH_CHECK_ACTION = 'health_check'
RECOMMENDATION_ACTION = 'recommendation'
LM_SETTING_CONFIG_ACTION = 'settings-config'
LM_SETTING_CLIENT_ACTION = 'settings-client'
LICENSE_ACTION = 'license'
LICENSE_SYNC_ACTION = 'license-sync'
GROUP_POLICY_ACTION = 'group-policy'


class R8sApiHandler(AbstractApiHandlerLambda):
    def __init__(self, user_service: CognitoUserService,
                 access_control_service: AccessControlService,
                 algorithm_service: AlgorithmService, iam_service: IamService,
                 storage_service: StorageService,
                 environment_service: EnvironmentService,
                 batch_client: BatchClient,
                 job_service: JobService, report_service: ReportService,
                 customer_service: CustomerService,
                 tenant_service: TenantService,
                 settings_service: SettingsService,
                 shape_service: ShapeService,
                 shape_price_service: ShapePriceService,
                 application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 ssm_service: SSMService,
                 api_gateway_client: ApiGatewayClient,
                 s3_client: S3Client,
                 shape_rules_filter_service: ShapeRulesFilterService,
                 recommendation_history_service: RecommendationHistoryService,
                 lambda_client: LambdaClient,
                 customer_preferences_service: CustomerPreferencesService,
                 resize_service: ResizeService,
                 key_management_service: KeyManagementService,
                 license_manager_service: LicenseManagerService,
                 license_service: LicenseService):
        self.user_service = user_service
        self.access_control_service = access_control_service
        self.algorithm_service = algorithm_service
        self.iam_service = iam_service
        self.storage_service = storage_service
        self.environment_service = environment_service
        self.batch_client = batch_client
        self.job_service = job_service
        self.report_service = report_service
        self.customer_service = customer_service
        self.tenant_service = tenant_service
        self.settings_service = settings_service
        self.shape_service = shape_service
        self.shape_price_service = shape_price_service
        self.application_service = application_service
        self.parent_service = parent_service
        self.ssm_service = ssm_service
        self.api_gateway_client = api_gateway_client
        self.s3_client = s3_client
        self.shape_rules_filter_service = shape_rules_filter_service
        self.recommendation_history_service = recommendation_history_service
        self.lambda_client = lambda_client
        self.customer_preferences_service = customer_preferences_service
        self.resize_service = resize_service
        self.key_management_service = key_management_service
        self.license_manager_service = license_manager_service
        self.license_service = license_service

        self.processor_registry = {
            SIGNIN_ACTION: self._instantiate_signin_processor,
            REFRESH_ACTION: self._instantiate_refresh_processor,
            SIGNUP_ACTION: self._instantiate_signup_processor,
            POLICY_ACTION: self._instantiate_policy_processor,
            ROLE_ACTION: self._instantiate_role_processor,
            ALGORITHM_ACTION: self._instantiate_algorithm_processor,
            STORAGE_ACTION: self._instantiate_storage_processor,
            APPLICATION_ACTION: self._instantiate_application_processor,
            APPLICATION_LICENSES_ACTION:
                self._instantiate_application_licenses_processor,
            APPLICATION_DOJO_ACTION:
                self._instantiate_application_dojo_processor,
            JOB_ACTION: self._instantiate_job_processor,
            REPORT_ACTION: self._instantiate_report_processor,
            MAIL_REPORT_ACTION: self._instantiate_mail_report_processor,
            STORAGE_DATA_ACTION: self._instantiate_storage_data_processor,
            SHAPE_RULE_ACTION: self._instantiate_shape_rule_processor,
            SHAPE_RULE_DRY_RUN_ACTION:
                self._instantiate_shape_rule_dry_run_processor,
            PARENT_ACTION: self._instantiate_parent_processor,
            PARENT_DOJO_ACTION: self._instantiate_dojo_parent_processor,
            USER_ACTION: self._instantiate_user_processor,
            SHAPE_ACTION: self._instantiate_shape_processor,
            SHAPE_PRICE_ACTION: self._instantiate_shape_price_processor,
            HEALTH_CHECK_ACTION: self._instantiate_health_check_processor,
            RECOMMENDATION_ACTION: self._instantiate_recommendation_processor,
            PARENT_INSIGHTS_RESIZE_ACTION:
                self._instantiate_resize_insights_processor,
            LM_SETTING_CONFIG_ACTION: self._instantiate_lm_config_processor,
            LM_SETTING_CLIENT_ACTION: self._instantiate_lm_client_processor,
            LICENSE_ACTION: self._instantiate_license_processor,
            LICENSE_SYNC_ACTION: self._instantiate_license_sync_processor,
            GROUP_POLICY_ACTION: self._instantiate_group_policy_processor
        }

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
        action_processor_builder = self.processor_registry.get(action_name)
        if not action_processor_builder:
            error_message = f'There is no handler for ' \
                            f'action {action_name}'
            _LOG.info(f'request handle error: {error_message}')
            raise_error_response(content=error_message, code=400)
        processor = action_processor_builder()
        result = processor.handle_command(event=event)
        return result

    def _instantiate_signup_processor(self):
        return SignUpProcessor(
            user_service=self.user_service,
            access_control_service=self.access_control_service,
        )

    def _instantiate_signin_processor(self):
        return SignInProcessor(
            user_service=self.user_service,
        )

    def _instantiate_refresh_processor(self):
        return RefreshProcessor(
            user_service=self.user_service,
        )

    def _instantiate_policy_processor(self):
        return PolicyProcessor(
            user_service=self.user_service,
            access_control_service=self.access_control_service,
            iam_service=self.iam_service
        )

    def _instantiate_role_processor(self):
        return RoleProcessor(
            user_service=self.user_service,
            access_control_service=self.access_control_service,
            iam_service=self.iam_service,
            customer_service=self.customer_service
        )

    def _instantiate_algorithm_processor(self):
        return AlgorithmProcessor(
            algorithm_service=self.algorithm_service,
            customer_service=self.customer_service
        )

    def _instantiate_storage_processor(self):
        return StorageProcessor(
            storage_service=self.storage_service
        )

    def _instantiate_application_processor(self):
        return ApplicationProcessor(
            application_service=self.application_service,
            parent_service=self.parent_service,
            algorithm_service=self.algorithm_service,
            storage_service=self.storage_service,
            customer_service=self.customer_service,
            api_gateway_client=self.api_gateway_client
        )

    def _instantiate_application_licenses_processor(self):
        return ApplicationLicensesProcessor(
            algorithm_service=self.algorithm_service,
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service,
            license_service=self.license_service,
            license_manager_service=self.license_manager_service
        )

    def _instantiate_application_dojo_processor(self):
        return DojoApplicationProcessor(
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service
        )

    def _instantiate_job_processor(self):
        return JobProcessor(
            application_service=self.application_service,
            job_service=self.job_service,
            environment_service=self.environment_service,
            customer_service=self.customer_service,
            tenant_service=self.tenant_service,
            settings_service=self.settings_service,
            shape_service=self.shape_service,
            shape_price_service=self.shape_price_service,
            parent_service=self.parent_service,
            license_service=self.license_service,
            license_manager_service=self.license_manager_service
        )

    def _instantiate_report_processor(self):
        return ReportProcessor(
            job_service=self.job_service,
            report_service=self.report_service,
            tenant_service=self.tenant_service
        )

    def _instantiate_storage_data_processor(self):
        return StorageDataProcessor(
            storage_service=self.storage_service,
            tenant_service=self.tenant_service
        )

    def _instantiate_shape_rule_processor(self):
        return ShapeRuleProcessor(
            application_service=self.application_service,
            parent_service=self.parent_service,
            tenant_service=self.tenant_service
        )

    def _instantiate_shape_rule_dry_run_processor(self):
        return ShapeRuleDryRunProcessor(
            application_service=self.application_service,
            parent_service=self.parent_service,
            shape_service=self.shape_service,
            shape_rules_filter_service=self.shape_rules_filter_service,
            tenant_service=self.tenant_service
        )

    def _instantiate_parent_processor(self):
        return ParentProcessor(
            algorithm_service=self.algorithm_service,
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service,
            tenant_service=self.tenant_service,
            license_service=self.license_service,
            license_manager_service=self.license_manager_service
        )

    def _instantiate_dojo_parent_processor(self):
        return DojoParentProcessor(
            customer_service=self.customer_service,
            application_service=self.application_service,
            parent_service=self.parent_service,
            tenant_service=self.tenant_service
        )

    def _instantiate_shape_processor(self):
        return ShapeProcessor(
            shape_service=self.shape_service,
            shape_price_service=self.shape_price_service
        )

    def _instantiate_shape_price_processor(self):
        return ShapePriceProcessor(
            shape_service=self.shape_service,
            shape_price_service=self.shape_price_service,
            customer_service=self.customer_service
        )

    def _instantiate_user_processor(self):
        return UserProcessor(
            user_service=self.user_service,
            access_control_service=self.access_control_service,
            iam_service=self.iam_service
        )

    def _instantiate_health_check_processor(self):
        return HealthCheckProcessor(
            application_service=self.application_service,
            tenant_service=self.tenant_service,
            shape_service=self.shape_service,
            shape_price_service=self.shape_price_service,
            parent_service=self.parent_service,
            storage_service=self.storage_service,
            ssm_service=self.ssm_service,
            api_gateway_client=self.api_gateway_client,
            user_service=self.user_service,
            algorithm_service=self.algorithm_service,
            s3_client=self.s3_client,
            settings_service=self.settings_service,
            environment_service=self.environment_service
        )

    def _instantiate_recommendation_processor(self):
        return RecommendationHistoryProcessor(
            recommendation_history_service=self.recommendation_history_service
        )

    def _instantiate_mail_report_processor(self):
        return MailReportProcessor(
            lambda_client=self.lambda_client
        )

    def _instantiate_resize_insights_processor(self):
        return ParentResizeInsightsProcessor(
            parent_service=self.parent_service,
            algorithm_service=self.algorithm_service,
            shape_service=self.shape_service,
            customer_preferences_service=self.customer_preferences_service,
            resize_service=self.resize_service
        )

    def _instantiate_lm_config_processor(self):
        return LicenseManagerConfigProcessor(
            settings_service=self.settings_service
        )

    def _instantiate_lm_client_processor(self):
        return LicenseManagerClientProcessor(
            settings_service=self.settings_service,
            license_manager_service=self.license_manager_service,
            key_management_service=self.key_management_service
        )

    def _instantiate_license_processor(self):
        return LicenseProcessor(
            license_service=self.license_service,
            algorithm_service=self.algorithm_service
        )

    def _instantiate_license_sync_processor(self):
        return LicenseSyncProcessor(
            license_service=self.license_service,
            license_manager_service=self.license_manager_service,
            algorithm_service=self.algorithm_service
        )

    def _instantiate_group_policy_processor(self):
        return GroupPolicyProcessor(
            application_service=self.application_service
        )


HANDLER = R8sApiHandler(
    user_service=SERVICE_PROVIDER.user_service(),
    access_control_service=SERVICE_PROVIDER.access_control_service(),
    algorithm_service=SERVICE_PROVIDER.algorithm_service(),
    iam_service=SERVICE_PROVIDER.iam_service(),
    storage_service=SERVICE_PROVIDER.storage_service(),
    environment_service=SERVICE_PROVIDER.environment_service(),
    batch_client=SERVICE_PROVIDER.batch(),
    job_service=SERVICE_PROVIDER.job_service(),
    report_service=SERVICE_PROVIDER.report_service(),
    customer_service=SERVICE_PROVIDER.customer_service(),
    tenant_service=SERVICE_PROVIDER.tenant_service(),
    settings_service=SERVICE_PROVIDER.settings_service(),
    shape_service=SERVICE_PROVIDER.shape_service(),
    shape_price_service=SERVICE_PROVIDER.shape_price_service(),
    application_service=SERVICE_PROVIDER.rightsizer_application_service(),
    parent_service=SERVICE_PROVIDER.rightsizer_parent_service(),
    ssm_service=SERVICE_PROVIDER.ssm_service(),
    api_gateway_client=SERVICE_PROVIDER.api_gateway_client(),
    s3_client=SERVICE_PROVIDER.s3(),
    shape_rules_filter_service=SERVICE_PROVIDER.shape_rules_filter_service(),
    recommendation_history_service=SERVICE_PROVIDER.recommendation_history_service(),
    lambda_client=SERVICE_PROVIDER.lambda_client(),
    customer_preferences_service=SERVICE_PROVIDER.customer_preferences_service(),
    resize_service=SERVICE_PROVIDER.resize_service(),
    key_management_service=SERVICE_PROVIDER.key_management_service(),
    license_manager_service=SERVICE_PROVIDER.license_manager_service(),
    license_service=SERVICE_PROVIDER.license_service()
)


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
