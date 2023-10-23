GET_METHOD = 'GET'
POST_METHOD = 'POST'
PATCH_METHOD = 'PATCH'
DELETE_METHOD = 'DELETE'

BODY_ATTR = 'body'
THRESHOLDS_ATTR = 'thresholds'
ALGORITHM_ATTR = 'algorithm'
EXPIRATION_ATTR = 'expiration'
TENANT_ATTR = 'tenant'
CUSTOMER_ATTR = 'customer'
VALUE_ATTR = 'value'

SERVICE_ATTR = 'service'

DATA_SOURCE_ATTR = 'data_source'
STORAGE_ATTR = 'storage'
MODEL_ATTR = 'model'
SCHEDULE_ATTR = 'schedule'
ANALYSIS_SPECS_ATTR = 'analysis_specs'
JOB_DEFINITION_ATTR = 'job_definition'
PARAM_NATIVE_JOB_ID = 'jobId'
SAVING_OPTIONS_ATTR = 'saving_options'
CURRENT_INSTANCE_TYPE_ATTR = 'current_instance_type'
CURRENT_MONTHLY_PRICE_ATTR = 'current_monthly_price_usd'

JOB_STEP_INITIALIZATION = 'INITIALIZATION'
JOB_STEP_DOWNLOAD_METRICS = 'DOWNLOAD_METRICS'
JOB_STEP_VALIDATE_METRICS = 'VALIDATE_METRICS'
JOB_STEP_INITIALIZE_ALGORITHM = 'INITIALIZE_ALGORITHM'
JOB_STEP_PROCESS_METRICS = 'PROCESS_METRICS'
JOB_STEP_GENERATE_REPORTS = 'GENERATE_REPORTS'

CSV_EXTENSION = '.csv'
META_FILE_NAME = 'meta_info.json'
MONGODB_CONNECTION_URI_PARAMETER = 'r8s_mongodb_connection_uri'

STATUS_OK = 'OK'
STATUS_ERROR = 'ERROR'
STATUS_POSTPONED = 'POSTPONED'
OK_MESSAGE = 'Processed successfully'

ACTION_SCHEDULE = 'SCHEDULE'
ACTION_SHUTDOWN = 'SHUTDOWN'
ACTION_SCALE_UP = 'SCALE_UP'
ACTION_SCALE_DOWN = 'SCALE_DOWN'
ACTION_CHANGE_SHAPE = 'CHANGE_SHAPE'
ACTION_SPLIT = 'SPLIT'
ACTION_EMPTY = 'NO_ACTION'
ACTION_ERROR = 'ERROR'

ALLOWED_ACTIONS = [ACTION_SCHEDULE, ACTION_SHUTDOWN, ACTION_SCALE_UP,
                   ACTION_SCALE_DOWN, ACTION_CHANGE_SHAPE, ACTION_SPLIT,
                   ACTION_EMPTY, ACTION_ERROR]

WORK_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
WEEKEND_DAYS = ['Saturday', 'Sunday']
WEEK_DAYS = WORK_DAYS + WEEKEND_DAYS

INSTANCE_SPECS_STORAGE_TYPE = 'INSTANCE_SPECS_STORAGE_TYPE'
STORAGE_TYPE_SETTING = 'SETTING'

COLUMN_CPU_LOAD = 'cpu_load'
COLUMN_MEMORY_LOAD = 'memory_load'

DEFAULT_DAYS_TO_PROCESS = 60

CLOUD_AWS = 'aws'
CLOUD_AZURE = 'azure'
CLOUD_GOOGLE = 'google'
CLOUD_ATTR = 'cloud'

CLOUDS = [CLOUD_AWS, CLOUD_AZURE, CLOUD_GOOGLE]

METRIC_FORMAT_ATTR = 'metric_format'
DELIMITER_ATTR = 'delimiter'
SKIP_INITIAL_SPACE_ATTR = 'skipinitialspace'
LINE_TERMINATOR_ATTR = 'lineterminator'
QUOTE_CHAR_ATTR = 'quotechar'
QUOTING_ATTR = 'quoting'
ESCAPE_CHAR_ATTR = 'escapechar'
DOUBLE_QUOTE_ATTR = 'doublequote'

METRIC_FORMAT_ATTRS = [DELIMITER_ATTR, SKIP_INITIAL_SPACE_ATTR,
                       LINE_TERMINATOR_ATTR, QUOTE_CHAR_ATTR, QUOTING_ATTR,
                       ESCAPE_CHAR_ATTR, DOUBLE_QUOTE_ATTR]

CLUSTERING_SETTINGS_ATTR = 'clustering_settings'
MAX_CLUSTERS_ATTR = 'max_clusters'
WCSS_KMEANS_INIT_ATTR = 'wcss_kmeans_init'
WCSS_KMEANS_MAX_ITER_ATTR = 'wcss_kmeans_max_iter'
WCSS_KMEANS_N_INIT_ATTR = 'wcss_kmeans_n_init'
KNEE_INTERP_METHOD_ATTR = 'knee_interp_method'
KNEE_POLYMONIAL_DEGREE_ATTR = 'knee_polynomial_degree'

CLUSTERING_SETTINGS_ATTRS = [
    MAX_CLUSTERS_ATTR, WCSS_KMEANS_INIT_ATTR, WCSS_KMEANS_N_INIT_ATTR,
    WCSS_KMEANS_MAX_ITER_ATTR, KNEE_INTERP_METHOD_ATTR,
    KNEE_POLYMONIAL_DEGREE_ATTR]

RECOMMENDATION_SETTINGS_ATTR = 'recommendation_settings'
RECORD_STEP_MINUTES_ATTR = 'record_step_minutes'
MIN_ALLOWED_DAYS_ATTR = 'min_allowed_days'
MAX_DAYS_ATTR = 'max_days'
MIN_ALLOWED_DAYS_SCHEDULE_ATTR = 'min_allowed_days_schedule'
IGNORE_SAVINGS_ATTR = 'ignore_savings'
MAX_RECOMMENDED_SHAPES_ATTR = 'max_recommended_shapes'
SHAPE_COMPATIBILITY_RULE_ATTR = 'shape_compatibility_rule'
SHAPE_SORTING_ATTR = 'shape_sorting'
USE_PAST_RECOMMENDATIONS_ATTR = 'use_past_recommendations'
USE_INSTANCE_TAGS_ATTR = 'use_instance_tags'
ANALYSIS_PRICE_ATTR = 'analysis_price'
IGNORE_ACTIONS_ATTR = 'ignore_actions'
TARGET_TIMEZONE_NAME_ATTR = 'target_timezone_name'

RECOMMENDATION_SETTINGS_ATTRS = [
    RECORD_STEP_MINUTES_ATTR, THRESHOLDS_ATTR, MIN_ALLOWED_DAYS_ATTR,
    MAX_DAYS_ATTR, MIN_ALLOWED_DAYS_SCHEDULE_ATTR, IGNORE_SAVINGS_ATTR,
    MAX_RECOMMENDED_SHAPES_ATTR, SHAPE_COMPATIBILITY_RULE_ATTR,
    SHAPE_SORTING_ATTR, USE_PAST_RECOMMENDATIONS_ATTR,
    USE_INSTANCE_TAGS_ATTR, ANALYSIS_PRICE_ATTR, TARGET_TIMEZONE_NAME_ATTR
]

RULE_ACTION_ALLOW = 'allow'
RULE_ACTION_DENY = 'deny'
RULE_ACTION_PRIORITIZE = 'prioritize'

ALLOWED_RULE_ACTIONS = (RULE_ACTION_ALLOW, RULE_ACTION_DENY,
                        RULE_ACTION_PRIORITIZE)

RULE_CONDITION_CONTAINS = 'contains'
RULE_CONDITION_NOT_CONTAINS = 'not_contains'
RULE_CONDITION_EQUALS = 'equals'
RULE_CONDITION_MATCHES = 'matches'
RULE_CONDITION_NOT_MATCHES = 'not_matches'

ALLOWED_RULE_CONDITIONS = (
    RULE_CONDITION_CONTAINS, RULE_CONDITION_NOT_CONTAINS,
    RULE_CONDITION_EQUALS, RULE_CONDITION_MATCHES, RULE_CONDITION_NOT_MATCHES)

ALLOWED_SHAPE_FIELDS = ('name', 'family_type', 'physical_processor',
                        'architecture')
PARENT_ID_ATTR = 'parent_id'
PARENT_SCOPE_ALL_TENANTS = 'ALL_TENANTS'
PARENT_SCOPE_SPECIFIC_TENANT = 'SPECIFIC_TENANT'
TENANT_PARENT_MAP_RIGHTSIZER_TYPE = 'RIGHTSIZER'
ALL = 'ALL'

DEFAULT_META_POSTPONED_KEY = 'postponedTill'
DEFAULT_META_POSTPONED_FOR_ACTIONS_KEY = 'actions'

ENV_SERVICE_MODE = 'SERVICE_MODE'
DOCKER_SERVICE_MODE, SAAS_SERVICE_MODE = 'docker', 'saas'

ENV_MONGODB_USER = 'MONGO_USER'
ENV_MONGODB_PASSWORD = 'MONGO_PASSWORD'
ENV_MONGODB_URL = 'MONGO_URL'  # host:port
ENV_MONGODB_DATABASE = 'MONGO_DATABASE'

ENV_MINIO_HOST = 'MINIO_HOST'
ENV_MINIO_PORT = 'MINIO_PORT'
ENV_MINIO_ACCESS_KEY = 'MINIO_ACCESS_KEY'
ENV_MINIO_SECRET_ACCESS_KEY = 'MINIO_SECRET_ACCESS_KEY'

ENV_VAULT_TOKEN = 'VAULT_TOKEN'
ENV_VAULT_HOST = 'VAULT_URL'
ENV_VAULT_PORT = 'VAULT_SERVICE_SERVICE_PORT'

ENV_FORCE_RESCAN = 'FORCE_RESCAN'
ENV_LM_TOKEN_LIFETIME_MINUTES = 'lm_token_lifetime_minutes'
JOB_ID = 'job_id'

# License Manager
CUSTOMERS_ATTR = 'customers'
TENANTS_ATTR = 'tenants'
ATTACHMENT_MODEL_ATTR = 'attachment_model'
LICENSE_KEY_ATTR = 'license_key'
LICENSE_KEYS_ATTR = 'license_keys'
TENANT_LICENSE_KEY_ATTR = 'tenant_license_key'
TENANT_LICENSE_KEYS_ATTR = 'tenant_license_keys'
AUTHORIZATION_PARAM = 'authorization'
STATUS_ATTR = 'status'
ALGORITHM_ID_ATTR = 'algorithm_id'

KID_ATTR = 'kid'
ALG_ATTR = 'alg'
TYP_ATTR = 'typ'

TOKEN_DATE_ATTR = 'token_date'
CLIENT_TOKEN_ATTR = 'client-token'
STAGE_ATTR = 'stage'
KEY_ID_ATTR = 'key_id'
B64ENCODED_ATTR = 'b64_encoded'

SERVICE_TYPE_ATTR = 'service_type'
SERVICE_TYPE_RIGHTSIZER = 'RIGHTSIZER'
ALGORITHMS_ATTR = 'algorithms'
TOKEN_ATTR = 'token'

RESPONSE_BAD_REQUEST_CODE = 400
RESPONSE_UNAUTHORIZED = 401
RESPONSE_FORBIDDEN_CODE = 403
RESPONSE_RESOURCE_NOT_FOUND_CODE = 404
RESPONSE_OK_CODE = 200

BODY_PARAM = 'body'
ITEMS_PARAM = 'items'
MESSAGE_PARAM = 'message'

PROFILE_LOG_PATH = f'/tmp/execution_log.txt'
