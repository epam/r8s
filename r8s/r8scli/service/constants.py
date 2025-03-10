PARAM_NAME = 'name'
PARAM_PERMISSIONS = 'permissions'
PARAM_PERMISSIONS_ADMIN = 'permissions_admin'
PARAM_EXPIRATION = 'expiration'
PARAM_POLICIES = 'policies'
PARAM_VERSION = 'version'
PARAM_CLOUD = 'cloud'
PARAM_CLOUDS = 'clouds'
PARAM_SUBMITTED_AT = 'submitted_at'
PARAM_CREATED_AT = 'created_at'
PARAM_STARTED_AT = 'started_at'
PARAM_STOPPED_AT = 'stopped_at'
PARAM_ACTIVE = 'active'
PARAM_ACTION = 'action'
PARAM_SCOPE = 'scope'
PARAM_LIMIT = 'limit'

PARAM_USERNAME = 'username'
PARAM_PASSWORD = 'password'
PARAM_REFRESH_TOKEN = 'refresh_token'
PARAM_TARGET_USER = 'target_user'

API_POLICY = 'policies'
API_ROLE = 'roles'
API_JOB = 'jobs'
API_REPORT = 'reports'
API_TENANT_MAIL_REPORT = 'reports/mail/tenant'
API_SIGNIN = 'signin'
API_REFRESH = 'refresh'
API_SIGNUP = 'signup'
API_ALGORITHM = 'algorithms'
API_STORAGE = 'storages'
API_STORAGE_DATA = 'storages/data'
API_USER = 'users'

PARAM_ID = '_id'
API_APPLICATION = 'applications'
API_APPLICATION_LICENSES = 'applications/licenses'
API_APPLICATION_POLICIES = 'applications/policies'
API_APPLICATION_DOJO = 'applications/dojo'
API_PARENT = 'parents'
API_PARENT_LICENSES = 'parents/licenses'
API_PARENT_DOJO = 'parents/dojo'
API_PARENT_TENANT_LINK = 'parents/tenant-link'
API_PARENT_INSIGHTS_RESIZE = 'parents/insights/resize'
API_SHAPE_RULES = 'parents/shape-rules'
API_SHAPE_RULES_DRY_RUN = 'parents/shape-rules/dry-run'
API_SHAPE = 'shapes'
API_SHAPE_PRICE = 'shapes/prices'
API_HEALTH_CHECK = 'health-check'
API_RECOMMENDATION = 'recommendations'
API_LICENSE = 'licenses'
API_LICENSE_SYNC = 'licenses/sync'
API_LM_CONFIG_SETTING = 'settings/license-manager/config'
API_LM_CLIENT_SETTING = 'settings/license-manager/client'
PARAM_ID = 'id'
PARAM_JOB_ID = 'job_id'

PARAM_TENANT = 'tenant'
PARAM_THRESHOLDS = 'thresholds'
PARAM_ALGORITHM = 'algorithm'
PARAM_STATUS = 'status'
PARAM_REQUIRED_DATA_ATTRS = 'required_data_attributes'
PARAM_METRIC_ATTRS = 'metric_attributes'
PARAM_TIMESTAMP_ATTR = 'timestamp_attribute'
PARAM_ACTION = 'action'
PARAM_BODY = 'body'
PARAM_TYPE = 'type'
PARAM_TYPES = 'types'
PARAM_SERVICE = 'service'
PARAM_BUCKET_NAME = 'bucket_name'
PARAM_PREFIX = 'prefix'
PARAM_ROLE = 'role'

PARAM_ACCESS = 'access'
PARAM_DATASOURCE = 'data_source'
PARAM_STORAGE = 'storage'
PARAM_SCHEDULE = 'schedule'
PARAM_ANALYSIS_SPECS = 'analysis_specs'
PARAM_EXPAND = 'expand'

PARAM_OWNER = 'owner'
PARAM_JOB_QUEUE = 'job_queue'

PARAM_INSTANCE_ID = 'instance_id'
PARAM_INSTANCE_TYPE = 'instance_type'
PARAM_INSTANCE_FAMILY = 'instance_family'
PARAM_LOCATION = 'location'
PARAM_VCPU = 'vCPU'
PARAM_MEMORY = 'memory'
PARAM_PRICE = 'price'
PARAM_OS = 'os'
PARAM_PRICE_MONTH = 'price_month'
PARAM_SAVINGS_MONTH = 'savings_month'
PARAM_CUSTOMER = 'customer'
PARAM_TENANT = 'tenant'
PARAM_TENANTS = 'tenants'
PARAM_REGION = 'region'
PARAM_RECOMMENDED_SHAPES = 'recommended_shapes'
PARAM_SCHEDULE = 'schedule'
PARAM_TIMESTAMP = 'timestamp'
PARAM_SCAN_FROM_DATE = 'scan_from_date'
PARAM_SCAN_TO_DATE = 'scan_to_date'
PARAM_SCAN_CLOUDS = 'scan_clouds'
PARAM_DETAILED = 'detailed'

PARAM_REPORT_TYPE = 'report_type'
REPORT_RESIZE = 'instance_shape'
REPORT_DOWNLOAD = 'download'

POLICIES_TO_ATTACH = 'policies_to_attach'
POLICIES_TO_DETACH = 'policies_to_detach'

PERMISSIONS_TO_ATTACH = 'permissions_to_attach'
PERMISSIONS_TO_DETACH = 'permissions_to_detach'

AVAILABLE_CLOUDS = ('AWS', 'AZURE', 'GOOGLE')
PARAM_API_VERSION = 'api_version'
SERVICE_S3_BUCKET = 'S3_BUCKET'
AVAILABLE_SERVICES = (SERVICE_S3_BUCKET,)
TYPE_STORAGE = 'STORAGE'
TYPE_DATASOURCE = 'DATA_SOURCE'
AVAILABLE_STORAGE_TYPES = (TYPE_STORAGE, TYPE_DATASOURCE)

PARAM_METRIC_FORMAT = 'metric_format'

PARAM_DELIMITER = 'delimiter'
PARAM_SKIP_INITIAL_SPACE = 'skipinitialspace'
PARAM_LINE_TERMINATOR = 'lineterminator'
PARAM_QUOTE_CHAR = 'quotechar'
PARAM_QUOTING = 'quoting'
PARAM_ESCAPE_CHAR = 'escapechar'
PARAM_DOUBLE_QUOTE = 'doublequote'

AVAILABLE_QUOTING = {
    'QUOTE_MINIMAL': 0,
    'QUOTE_ALL': 1,
    'QUOTE_NONNUMERIC': 2,
    'QUOTE_NONE': 3
}

PARAM_CLUSTERING_SETTINGS = 'clustering_settings'
PARAM_MAX_CLUSTERS = 'max_clusters'
PARAM_WCSS_KMEANS_INIT = 'wcss_kmeans_init'
PARAM_WCSS_KMEANS_MAX_ITER = 'wcss_kmeans_max_iter'
PARAM_WCSS_KMEANS_N_INIT = 'wcss_kmeans_n_init'
PARAM_KNEE_INTERP_METHOD = 'knee_interp_method'
PARAM_KNEE_POLYMONIAL_DEGREE = 'knee_polynomial_degree'

AVAILABLE_KNEE_INTERP_OPTIONS = ('polynomial', 'interp1d')
AVAILABLE_KMEANS_INIT = ('k-means++', 'random')

PARAM_RECOMMENDATION_SETTINGS = 'recommendation_settings'
PARAM_RECORD_STEP_MINUTES = 'record_step_minutes'
PARAM_THRESHOLDS = 'thresholds'
PARAM_MIN_ALLOWED_DAYS = 'min_allowed_days'
PARAM_MAX_DAYS = 'max_days'
PARAM_MIN_ALLOWED_DAYS_SCHEDULE = 'min_allowed_days_schedule'
PARAM_IGNORE_SAVINGS = 'ignore_savings'
PARAM_MAX_RECOMMENDED_SHAPES = 'max_recommended_shapes'
PARAM_SHAPE_COMPATIBILITY_RULE = 'shape_compatibility_rule'
PARAM_SHAPE_SORTING = 'shape_sorting'
PARAM_USE_PAST_RECOMMENDATIONS = 'use_past_recommendations'
PARAM_USE_INSTANCE_TAGS = 'use_instance_tags'
PARAM_ANALYSIS_PRICE = 'analysis_price'
PARAM_IGNORE_ACTIONS = 'ignore_actions'
PARAM_TARGET_TIMEZONE_NAME = 'target_timezone_name'
PARAM_DISCARD_INITIAL_ZEROS = 'discard_initial_zeros'
PARAM_FORBID_CHANGE_SERIES = 'forbid_change_series'
PARAM_FORBID_CHANGE_FAMILY = 'forbid_change_family'

AVAILABLE_SHAPE_COMPATIBILITY_RULES = ('NONE', 'SAME', 'COMPATIBLE')
AVAILABLE_SHAPE_SORTING = ('PRICE', 'PERFORMANCE')
AVAILABLE_ANALYSIS_PRICE = ('DEFAULT', 'CUSTOMER_MIN', 'CUSTOMER_AVG',
                            'CUSTOMER_MAX')

PARAM_RULE_ACTION = 'rule_action'
PARAM_APPLICATION_ID = 'application_id'
PARAM_PARENT_ID = 'parent_id'
PARAM_CONDITION = 'condition'
PARAM_FIELD = 'field'
PARAM_VALUE = 'value'

ALLOWED_RULE_ACTIONS = ('allow', 'deny', 'prioritize')

ALLOWED_RULE_CONDITIONS = (
    'contains', 'not_contains',
    'equals', 'matches', 'not_matches')

ALLOWED_SHAPE_FIELDS = ('name', 'family_type', 'physical_processor',
                        'architecture')

PARAM_DESCRIPTION = 'description'
PARAM_INPUT_STORAGE = 'input_storage'
PARAM_OUTPUT_STORAGE = 'output_storage'
PARAM_TENANT_LICENSE_KEY = 'tenant_license_key'
PARAM_CONNECTION = 'connection'
PARAM_HOST = 'host'
PARAM_PORT = 'port'
PARAM_PROTOCOL = 'protocol'
PARAM_STAGE = 'stage'
PARAM_API_KEY = 'api_key'

PROTOCOL_HTTP = 'HTTP'
PROTOCOL_HTTPS = 'HTTPS'
ALLOWED_PROTOCOLS = (PROTOCOL_HTTP, PROTOCOL_HTTPS)

PARAM_CPU = 'cpu'
PARAM_MEMORY = 'memory'
PARAM_NETWORK_THROUGHPUT = 'network_throughput'
PARAM_IOPS = 'iops'
PARAM_FAMILY_TYPE = 'family_type'
PARAM_PHYSICAL_PROCESSOR = 'physical_processor'
PARAM_ARCHITECTURE = 'architecture'
PARAM_ON_DEMAND = 'on_demand'

AVAILABLE_OS = ('WINDOWS', 'LINUX')

PARENT_SCOPE_ALL = 'ALL'
PARENT_SCOPE_SPECIFIC = 'SPECIFIC'
PARENT_SCOPE_DISABLED = 'DISABLED'
AVAILABLE_PARENT_SCOPES = (PARENT_SCOPE_ALL, PARENT_SCOPE_SPECIFIC,
                           PARENT_SCOPE_DISABLED)

PARAM_RECOMMENDATION_TYPE = 'recommendation_type'
PARAM_FEEDBACK_STATUS = 'feedback_status'

AVAILABLE_CHECK_TYPES = ('APPLICATION', 'PARENT', 'STORAGE',
                         'SHAPE', 'OPERATION_MODE', 'SHAPE_UPDATE_DATE')

AVAILABLE_RECOMMENDATION_TYPES = ('SCHEDULE', 'SHUTDOWN', 'SCALE_UP',
                                  'SCALE_DOWN', 'CHANGE_SHAPE', 'SPLIT')
AVAILABLE_FEEDBACK_STATUSES = ('APPLIED', 'DONT_RECOMMEND', 'WRONG',
                               'TOO_LARGE', 'TOO_SMALL',
                               'TOO_EXPENSIVE', 'TOO_WIDE')
PARAM_LICENSE_KEY = 'license_key'
PARAM_LM_HOST = 'host'
PARAM_LM_PORT = 'port'
PARAM_LM_VERSION = 'version'

PARAM_KEY_ID = 'key_id'
PARAM_PRIVATE_KEY = 'private_key'
PARAM_ALGORITHM = 'algorithm'
PARAM_FORMAT = 'format'
PARAM_B64ENCODED = 'b64_encoded'
PARAM_FORCE = 'force'

GROUP_POLICY_AUTO_SCALING = 'AUTO_SCALING'
PARAM_TAG = 'tag'
PARAM_MIN = 'min'
PARAM_MAX = 'max'
PARAM_DESIRED = 'desired'
PARAM_SCALE_STEP = 'scale_step'
SCAPE_STEP_AUTO_DETECT = 'AUTO_DETECT'
PARAM_COOLDOWN = 'cooldown_days'
