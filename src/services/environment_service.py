import os

from commons.constants import ENV_SERVICE_MODE, DOCKER_SERVICE_MODE, \
    MAIL_REPORT_DEFAULT_PROCESSING_DAYS, \
    MAIL_REPORT_DEFAULT_HIGH_PRIORITY_THRESHOLD, ENV_TENANT_CUSTOMER_INDEX, \
    ENV_LM_TOKEN_LIFETIME_MINUTES

DEFAULT_TENANTS_CUSTOMER_NAME_INDEX_RCU = 5
DEFAULT_LM_TOKEN_LIFETIME_MINUTES = 120


class EnvironmentService:
    @staticmethod
    def aws_region():
        region = os.environ.get('AWS_REGION')
        if not region:
            region = os.environ.get('AWS_DEFAULT_REGION', 'eu-central-1')
        return region

    @staticmethod
    def get_user_pool_name():
        return os.environ.get('cognito_user_pool_name')

    @staticmethod
    def get_batch_job_queue():
        return os.environ.get('r8s_job_queue')

    @staticmethod
    def get_batch_job_def():
        return os.environ.get('r8s_job_definition')

    @staticmethod
    def get_mongodb_connection_uri():
        return os.environ.get('mongodb_connection_uri')

    @staticmethod
    def is_debug():
        debug = os.environ.get('DEBUG', False)
        return debug and debug.lower() in ('y', 't', 'true')

    @staticmethod
    def meta_postponed_key():
        return os.environ.get('META_POSTPONED_KEY')

    @staticmethod
    def get_rabbitmq_application_id():
        return os.environ.get('RABBITMQ_APPLICATION_ID')

    @staticmethod
    def is_docker() -> bool:
        return os.environ.get(ENV_SERVICE_MODE) == DOCKER_SERVICE_MODE

    @staticmethod
    def lambdas_alias_name():
        return os.environ.get('lambdas_alias_name')

    @staticmethod
    def mail_report_process_days():
        try:
            return int(os.environ.get('mail_report_process_days'))
        except (TypeError, ValueError):
            return MAIL_REPORT_DEFAULT_PROCESSING_DAYS

    @staticmethod
    def mail_report_high_priority_threshold() -> int:
        try:
            return int(os.environ.get('mail_report_high_priority_threshold'))
        except (TypeError, ValueError):
            return MAIL_REPORT_DEFAULT_HIGH_PRIORITY_THRESHOLD

    @staticmethod
    def tenants_customer_name_index_rcu():
        return int(os.environ.get(ENV_TENANT_CUSTOMER_INDEX,
                                  DEFAULT_TENANTS_CUSTOMER_NAME_INDEX_RCU))

    @staticmethod
    def lm_token_lifetime_minutes():
        try:
            return int(os.environ.get(ENV_LM_TOKEN_LIFETIME_MINUTES,
                                      DEFAULT_LM_TOKEN_LIFETIME_MINUTES))
        except ValueError:
            return DEFAULT_LM_TOKEN_LIFETIME_MINUTES
