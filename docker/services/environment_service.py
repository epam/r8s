import os

from commons.constants import INSTANCE_SPECS_STORAGE_TYPE, \
    STORAGE_TYPE_SETTING, DEFAULT_DAYS_TO_PROCESS, CLOUDS, \
    DEFAULT_META_POSTPONED_KEY, DEFAULT_META_POSTPONED_FOR_ACTIONS_KEY, \
    ENV_SERVICE_MODE, DOCKER_SERVICE_MODE


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
    def get_scan_customer():
        return os.environ.get('SCAN_CUSTOMER')

    @staticmethod
    def get_scan_tenants():
        raw = os.environ.get('SCAN_TENANTS')
        if raw:
            return raw.split(',')

    @staticmethod
    def get_scan_clouds():
        raw = os.environ.get('SCAN_CLOUDS')
        if not raw:
            return CLOUDS
        clouds = [cloud.strip().lower() for cloud in raw.split(',')
                  if cloud.strip()]
        clouds = [cloud for cloud in clouds if cloud in CLOUDS]
        if not clouds:
            return CLOUDS
        return clouds

    @staticmethod
    def get_scan_timestamp():
        return os.environ.get('SCAN_TIMESTAMP')

    @staticmethod
    def get_instance_specs_storage_type():
        return os.environ.get(INSTANCE_SPECS_STORAGE_TYPE,
                              STORAGE_TYPE_SETTING)

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
