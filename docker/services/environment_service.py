import os

from commons.constants import INSTANCE_SPECS_STORAGE_TYPE, \
    STORAGE_TYPE_SETTING, DEFAULT_DAYS_TO_PROCESS, DEFAULT_META_POSTPONED_KEY, \
    DEFAULT_META_POSTPONED_FOR_ACTIONS_KEY, \
    ENV_SERVICE_MODE, DOCKER_SERVICE_MODE, ENV_FORCE_RESCAN, \
    ENV_LM_TOKEN_LIFETIME_MINUTES, PARENT_ID_ATTR, APPLICATION_ID_ATTR, \
    LICENSED_APPLICATION_ID_ATTR

DEFAULT_LM_TOKEN_LIFETIME_MINUTES = 120


class EnvironmentService:
    @staticmethod
    def aws_region():
        return os.environ.get('AWS_REGION')

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
    def get_batch_job_id():
        return os.environ.get('AWS_BATCH_JOB_ID')

    @staticmethod
    def get_scan_from_date():
        return os.environ.get('SCAN_FROM_DATE')

    @staticmethod
    def get_scan_to_date():
        return os.environ.get('SCAN_TO_DATE')

    @staticmethod
    def get_instance_specs_storage_type():
        return os.environ.get(INSTANCE_SPECS_STORAGE_TYPE,
                              STORAGE_TYPE_SETTING)

    @staticmethod
    def get_application_id():
        return os.environ.get(APPLICATION_ID_ATTR)

    @staticmethod
    def get_licensed_application_id():
        return os.environ.get(LICENSED_APPLICATION_ID_ATTR)

    @staticmethod
    def get_licensed_parent_id():
        return os.environ.get(PARENT_ID_ATTR)

    @staticmethod
    def is_debug():
        debug = os.environ.get('DEBUG', False)
        return debug and debug.lower() in ('y', 't', 'true')

    @staticmethod
    def max_days_to_process():
        try:
            max_days = int(os.environ.get('MAX_DAYS_TO_PROCESS'))
        except (ValueError, TypeError):
            max_days = DEFAULT_DAYS_TO_PROCESS
        return max_days

    @staticmethod
    def meta_postponed_key():
        return os.environ.get('META_POSTPONED_KEY',
                              DEFAULT_META_POSTPONED_KEY)

    @staticmethod
    def meta_postponed_for_actions_key():
        return os.environ.get('META_POSTPONED_FOR_ACTIONS_KEY',
                              DEFAULT_META_POSTPONED_FOR_ACTIONS_KEY)

    @staticmethod
    def is_docker() -> bool:
        return os.environ.get(ENV_SERVICE_MODE) == DOCKER_SERVICE_MODE

    @staticmethod
    def force_rescan() -> bool:
        force_rescan = os.environ.get(ENV_FORCE_RESCAN, False)
        return force_rescan and force_rescan.lower() in ('y', 't', 'true')

    @staticmethod
    def lm_token_lifetime_minutes():
        try:
            return int(os.environ.get(ENV_LM_TOKEN_LIFETIME_MINUTES,
                                      DEFAULT_LM_TOKEN_LIFETIME_MINUTES))
        except ValueError:
            return DEFAULT_LM_TOKEN_LIFETIME_MINUTES
