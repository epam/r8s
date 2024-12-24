import json

import requests
from r8scli.service.constants import *
from r8scli.service.local_response_processor import LocalCommandResponse
from r8scli.service.logger import get_logger, get_user_logger

HTTP_GET = 'get'
HTTP_POST = 'post'
HTTP_PATCH = 'patch'
HTTP_DELETE = 'delete'

ALLOWED_METHODS = [HTTP_GET, HTTP_POST, HTTP_PATCH, HTTP_DELETE]

SYSTEM_LOG = get_logger('r8s.service.adapter_client')
USER_LOG = get_user_logger('user')


class AdapterClient:

    def __init__(self, adapter_api, token, refresh_token):
        self.__api_link = adapter_api
        self.__token = token
        self.__refresh_token = refresh_token
        self.__method_to_function = {
            HTTP_GET: requests.get,
            HTTP_POST: requests.post,
            HTTP_PATCH: requests.patch,
            HTTP_DELETE: requests.delete
        }
        SYSTEM_LOG.info('adapter SDK has been initialized')

    def __make_request(self, resource: str, method: str, payload: dict = None):
        if method not in ALLOWED_METHODS:
            SYSTEM_LOG.error(f'Requested method {method} in not allowed. '
                             f'Allowed methods: {ALLOWED_METHODS}')
            USER_LOG.error('Sorry, error happened. '
                           'Please contact the tool support team.')
        method_func = self.__method_to_function.get(method)
        parameters = dict(url=f'{self.__api_link}/{resource}')
        if method == HTTP_GET:
            parameters.update(params=payload)
        else:
            parameters.update(json=payload)
        SYSTEM_LOG.debug(f'API request info: {parameters}; Method: {method}')
        parameters.update(
            headers={'authorization': self.__token})
        try:
            response = method_func(**parameters)
            response.json()
        except requests.exceptions.ConnectionError:
            response = {
                'message': 'Provided configuration api_link is invalid '
                           'or outdated. Please contact the tool support team.'
            }
            return response
        except requests.exceptions.JSONDecodeError:
            response = {
                'message': 'Malformed response obtained. '
                           'Please contact the tool support team.'
            }
            return response

        SYSTEM_LOG.debug(f'API response info: {response}')
        return response

    def register(self, username, password, customer, role_name):
        request = {
            PARAM_USERNAME: username,
            PARAM_PASSWORD: password,
            PARAM_CUSTOMER: customer,
            PARAM_ROLE: role_name
        }
        response = self.__make_request(
            resource=API_SIGNUP,
            method=HTTP_POST,
            payload=request
        )
        return response

    def login(self, username, password):
        request = {
            PARAM_USERNAME: username,
            PARAM_PASSWORD: password
        }
        response = self.__make_request(
            resource=API_SIGNIN,
            method=HTTP_POST,
            payload=request
        )
        if isinstance(response, dict):
            return LocalCommandResponse(code=400, body=response)
        if response.status_code != 200:
            if 'password' in response.text:
                resp = LocalCommandResponse(
                    code=response.status_code,
                    body={"message": "Provided credentials are invalid."}
                )
                return resp
            else:
                SYSTEM_LOG.error(f'Error: {response.text}')
                return LocalCommandResponse(
                    code=response.status_code,
                    body={'message': 'Malformed response obtained. '
                                     'Please contact support team '
                                     'for assistance.'}
                )
        response = response.json()
        access_token = response.get('items')[0].get('id_token')
        refresh_token = response.get('items')[0].get('refresh_token')
        if not isinstance(access_token, str):
            return LocalCommandResponse(
                body={"message": "Mailformed response obtained. "
                                 "Please check your configuration."},
                code=400)
        return access_token, refresh_token

    def refresh(self):
        request = {
            PARAM_REFRESH_TOKEN: self.__refresh_token
        }
        response = self.__make_request(
            resource=API_REFRESH,
            method=HTTP_POST,
            payload=request
        )
        if isinstance(response, dict):
            return LocalCommandResponse(code=400, body=response)
        if response.status_code != 200:
            if 'Invalid refresh token' in response.text:
                resp = LocalCommandResponse(
                    code=response.status_code,
                    body={"message": "Invalid refresh token provided."}
                )
                return resp
            else:
                SYSTEM_LOG.error(f'Error: {response.text}')
                return LocalCommandResponse(
                    code=response.status_code,
                    body={'message': 'Malformed response obtained. '
                                     'Please contact support team '
                                     'for assistance.'}
                )
        response = response.json()
        response = response.get('items')[0]

        if isinstance(response, dict) and 'id_token' in response:
            return response
        else:
            return LocalCommandResponse(
                body={"message": "Malformed response obtained. "
                                 "Please check your configuration."},
                code=400)

    def policy_get(self, policy_name):
        request = {}
        if policy_name:
            request[PARAM_NAME] = policy_name
        return self.__make_request(resource=API_POLICY, method=HTTP_GET,
                                   payload=request)

    def policy_post(self, policy_name, permissions,
                    permissions_admin, path_to_permissions):
        request = {PARAM_NAME: policy_name}
        if permissions:
            request[PARAM_PERMISSIONS] = permissions
        if permissions_admin:
            request[PARAM_PERMISSIONS_ADMIN] = True
        if path_to_permissions:
            content = self.__get_permissions_from_file(path_to_permissions)
            if isinstance(content, dict):
                return content
            if request.get(PARAM_PERMISSIONS):
                request[PARAM_PERMISSIONS].extend(content)
            else:
                request[PARAM_PERMISSIONS] = content
        return self.__make_request(resource=API_POLICY, method=HTTP_POST,
                                   payload=request)

    @staticmethod
    def __get_permissions_from_file(path_to_permissions):
        try:
            with open(path_to_permissions, 'r') as file:
                content = json.load(file)
        except json.decoder.JSONDecodeError:
            message = {'message': 'Invalid file content'}
            return LocalCommandResponse(body=message, code=400)
        if isinstance(content, dict):
            content = content.get('permissions', [])
        if not isinstance(content, list):
            message = {'message': 'Invalid file content. Content of the json '
                                  'file must either be a list, or a dict with '
                                  '\'permissions\' key as list'}
            return LocalCommandResponse(body=message, code=400)
        return content

    def policy_patch(self, policy_name, attach_permissions,
                     detach_permissions):
        request = {PARAM_NAME: policy_name}
        if attach_permissions:
            request[PERMISSIONS_TO_ATTACH] = attach_permissions
        if detach_permissions:
            request[PERMISSIONS_TO_DETACH] = detach_permissions
        return self.__make_request(resource=API_POLICY, method=HTTP_PATCH,
                                   payload=request)

    def policy_delete(self, policy_name):
        request = {PARAM_NAME: policy_name}
        return self.__make_request(resource=API_POLICY, method=HTTP_DELETE,
                                   payload=request)

    def role_get(self, role_name):
        request = {}
        if role_name:
            request[PARAM_NAME] = role_name
        return self.__make_request(resource=API_ROLE, method=HTTP_GET,
                                   payload=request)

    def role_post(self, role_name, expiration, policies):
        request = {PARAM_NAME: role_name,
                   PARAM_POLICIES: policies}
        if expiration:
            request[PARAM_EXPIRATION] = expiration
        return self.__make_request(resource=API_ROLE, method=HTTP_POST,
                                   payload=request)

    def role_patch(self, role_name, expiration,
                   attach_policies,
                   detach_policies):
        request = {PARAM_NAME: role_name}
        if expiration:
            request[PARAM_EXPIRATION] = expiration
        if attach_policies:
            request[POLICIES_TO_ATTACH] = attach_policies
        if detach_policies:
            request[POLICIES_TO_DETACH] = detach_policies
        request = {k: v for k, v in request.items() if v}
        return self.__make_request(resource=API_ROLE, method=HTTP_PATCH,
                                   payload=request)

    def role_delete(self, role_name):
        request = {PARAM_NAME: role_name}
        return self.__make_request(resource=API_ROLE, method=HTTP_DELETE,
                                   payload=request)

    def user_get(self, username):
        request = {}
        if username:
            request[PARAM_TARGET_USER] = username
        return self.__make_request(resource=API_USER, method=HTTP_GET,
                                   payload=request)

    def user_patch(self, username, password):
        request = {
            PARAM_TARGET_USER: username,
            PARAM_PASSWORD: password
        }
        return self.__make_request(resource=API_USER, method=HTTP_PATCH,
                                   payload=request)

    def user_delete(self, username):
        request = {
            PARAM_TARGET_USER: username,
        }
        return self.__make_request(resource=API_USER, method=HTTP_DELETE,
                                   payload=request)

    def algorithm_get(self, algorithm_name):
        request = {}
        if algorithm_name:
            request[PARAM_NAME] = algorithm_name
        return self.__make_request(resource=API_ALGORITHM, method=HTTP_GET,
                                   payload=request)

    def algorithm_post(self, algorithm_name, customer, cloud, data_attributes,
                       metric_attributes, timestamp_attribute):
        request = {
            PARAM_NAME: algorithm_name,
            PARAM_CUSTOMER: customer,
            PARAM_CLOUD: cloud,
            PARAM_REQUIRED_DATA_ATTRS: data_attributes,
            PARAM_METRIC_ATTRS: metric_attributes,
            PARAM_TIMESTAMP_ATTR: timestamp_attribute
        }
        return self.__make_request(resource=API_ALGORITHM,
                                   method=HTTP_POST,
                                   payload=request)

    def algorithm_pathc_general_settings(self, algorithm_name, data_attribute,
                                         metric_attribute,
                                         timestamp_attribute):
        request = {
            PARAM_NAME: algorithm_name,
            PARAM_REQUIRED_DATA_ATTRS: data_attribute,
            PARAM_METRIC_ATTRS: metric_attribute,
            PARAM_TIMESTAMP_ATTR: timestamp_attribute
        }
        request = {k: v for k, v in request.items() if v is not None}

        return self.__make_request(resource=API_ALGORITHM,
                                   method=HTTP_PATCH,
                                   payload=request)

    def algorithm_patch_metric_format(self, algorithm_name, delimiter=None,
                                      skipinitialspace=None,
                                      lineterminator=None, quotechar=None,
                                      quoting=None, escapechar=None,
                                      doublequote=None):
        request = {
            PARAM_NAME: algorithm_name,
        }
        metric_format = {
            PARAM_DELIMITER: delimiter,
            PARAM_SKIP_INITIAL_SPACE: skipinitialspace,
            PARAM_LINE_TERMINATOR: lineterminator,
            PARAM_QUOTE_CHAR: quotechar,
            PARAM_QUOTING: AVAILABLE_QUOTING.get(quoting),
            PARAM_ESCAPE_CHAR: escapechar,
            PARAM_DOUBLE_QUOTE: doublequote,
        }
        metric_format = {k: v for k, v in metric_format.items() if
                         v is not None}
        request[PARAM_METRIC_FORMAT] = metric_format
        return self.__make_request(resource=API_ALGORITHM,
                                   method=HTTP_PATCH,
                                   payload=request)

    def algorithm_patch_clustering_settings(
            self, algorithm_name, max_clusters=None,
            wcss_kmeans_init=None,
            wcss_kmeans_max_iter=None, wcss_kmeans_n_init=None,
            knee_interp_method=None, knee_polynomial_degree=None):
        request = {
            PARAM_NAME: algorithm_name,
        }
        clustering_settings = {
            PARAM_MAX_CLUSTERS: max_clusters,
            PARAM_WCSS_KMEANS_INIT: wcss_kmeans_init,
            PARAM_WCSS_KMEANS_MAX_ITER: wcss_kmeans_max_iter,
            PARAM_WCSS_KMEANS_N_INIT: wcss_kmeans_n_init,
            PARAM_KNEE_INTERP_METHOD: knee_interp_method,
            PARAM_KNEE_POLYMONIAL_DEGREE: knee_polynomial_degree,
        }
        clustering_settings = {k: v for k, v in clustering_settings.items() if
                               v is not None}
        request[PARAM_CLUSTERING_SETTINGS] = clustering_settings
        return self.__make_request(resource=API_ALGORITHM,
                                   method=HTTP_PATCH,
                                   payload=request)

    def algorithm_patch_recommendation_settings(
            self, algorithm_name, record_step_minutes=None,
            thresholds=None,
            min_allowed_days=None, max_days=None,
            min_allowed_days_schedule=None,
            ignore_savings=None,
            max_recommended_shapes=None,
            shape_compatibility_rule=None,
            shape_sorting=None,
            use_past_recommendations=None,
            use_instance_tags=None,
            analysis_price=None,
            ignore_actions=None,
            target_timezone_name=None,
            discard_initial_zeros=None,
            forbid_change_family=None,
            forbid_change_series=None
    ):
        request = {
            PARAM_NAME: algorithm_name,
        }
        recommendation_settings = {
            PARAM_RECORD_STEP_MINUTES: record_step_minutes,
            PARAM_THRESHOLDS: thresholds,
            PARAM_MIN_ALLOWED_DAYS: min_allowed_days,
            PARAM_MAX_DAYS: max_days,
            PARAM_MIN_ALLOWED_DAYS_SCHEDULE: min_allowed_days_schedule,
            PARAM_IGNORE_SAVINGS: ignore_savings,
            PARAM_MAX_RECOMMENDED_SHAPES: max_recommended_shapes,
            PARAM_SHAPE_COMPATIBILITY_RULE: shape_compatibility_rule,
            PARAM_SHAPE_SORTING: shape_sorting,
            PARAM_USE_PAST_RECOMMENDATIONS: use_past_recommendations,
            PARAM_USE_INSTANCE_TAGS: use_instance_tags,
            PARAM_ANALYSIS_PRICE: analysis_price,
            PARAM_IGNORE_ACTIONS: ignore_actions,
            PARAM_TARGET_TIMEZONE_NAME: target_timezone_name,
            PARAM_DISCARD_INITIAL_ZEROS: discard_initial_zeros,
            PARAM_FORBID_CHANGE_SERIES: forbid_change_series,
            PARAM_FORBID_CHANGE_FAMILY: forbid_change_family
        }
        recommendation_settings = {k: v for k, v
                                   in recommendation_settings.items() if
                                   v is not None and v != []}
        request[PARAM_RECOMMENDATION_SETTINGS] = recommendation_settings
        return self.__make_request(resource=API_ALGORITHM,
                                   method=HTTP_PATCH,
                                   payload=request)

    def algorithm_delete(self, algorithm_name):
        request = {PARAM_NAME: algorithm_name}
        return self.__make_request(resource=API_ALGORITHM,
                                   method=HTTP_DELETE,
                                   payload=request)

    def storage_get(self, storage_name):
        request = {}
        if storage_name:
            request[PARAM_NAME] = storage_name
        return self.__make_request(resource=API_STORAGE, method=HTTP_GET,
                                   payload=request)

    def storage_post(self, storage_name, service, type, access):
        request = {
            PARAM_NAME: storage_name,
            PARAM_SERVICE: service,
            PARAM_TYPE: type,
            PARAM_ACCESS: access,
        }

        return self.__make_request(resource=API_STORAGE, method=HTTP_POST,
                                   payload=request)

    def storage_patch(self, storage_name, type, access):
        request = {
            PARAM_NAME: storage_name,
            PARAM_TYPE: type,
        }
        if access:
            request[PARAM_ACCESS] = access
        request = {k: v for k, v in request.items() if v is not None}
        return self.__make_request(resource=API_STORAGE, method=HTTP_PATCH,
                                   payload=request)

    def storage_delete(self, storage_name):
        request = {PARAM_NAME: storage_name}
        return self.__make_request(resource=API_STORAGE, method=HTTP_DELETE,
                                   payload=request)

    def storage_describe_metrics(self, data_source_name, tenant,
                                 region=None, timestamp=None,
                                 instance_id=None, customer=None):
        request = {
            PARAM_DATASOURCE: data_source_name,
            PARAM_TENANT: tenant,
            PARAM_REGION: region,
            PARAM_TIMESTAMP: timestamp,
            PARAM_INSTANCE_ID: instance_id,
            PARAM_CUSTOMER: customer,
        }
        request = {k: v for k, v in request.items() if v is not None}
        return self.__make_request(resource=API_STORAGE_DATA, method=HTTP_GET,
                                   payload=request)

    def job_get(self, job_id, job_name, limit):
        request = {}
        if job_id:
            request[PARAM_ID] = job_id
        elif job_name:
            request[PARAM_NAME] = job_name

        if limit:
            request[PARAM_LIMIT] = limit
        return self.__make_request(resource=API_JOB,
                                   method=HTTP_GET,
                                   payload=request)

    def job_post(self, application_id, parent_id,
                 scan_tenants, scan_from_date, scan_to_date):
        request = {
            PARAM_APPLICATION_ID: application_id,
            PARAM_PARENT_ID: parent_id,
            PARAM_TENANTS: scan_tenants,
            PARAM_SCAN_FROM_DATE: scan_from_date,
            PARAM_SCAN_TO_DATE: scan_to_date,
        }

        request = {k: v for k, v in request.items()}
        return self.__make_request(resource=API_JOB,
                                   method=HTTP_POST,
                                   payload=request)

    def job_delete(self, job_id):
        request = {
            PARAM_ID: job_id
        }
        return self.__make_request(resource=API_JOB,
                                   method=HTTP_DELETE,
                                   payload=request)

    def report_describe_general(self, job_id, customer, cloud, tenant,
                                region, instance_id, detailed):
        request = {
            PARAM_ID: job_id,
            PARAM_CUSTOMER: customer,
            PARAM_CLOUD: cloud,
            PARAM_TENANT: tenant,
            PARAM_REGION: region,
            PARAM_INSTANCE_ID: instance_id,
            PARAM_DETAILED: detailed
        }
        request = {k: v for k, v in request.items() if v is not None}
        return self.__make_request(resource=API_REPORT,
                                   method=HTTP_GET,
                                   payload=request)

    def report_describe_download(self, job_id, customer, tenant, region):
        request = {
            PARAM_REPORT_TYPE: REPORT_DOWNLOAD,
            PARAM_ID: job_id,
            PARAM_CUSTOMER: customer,
            PARAM_TENANT: tenant,
            PARAM_REGION: region
        }
        return self.__make_request(resource=API_REPORT,
                                   method=HTTP_GET,
                                   payload=request)

    def initiate_tenant_mail_report(self, customer, tenants):
        request = {
            PARAM_CUSTOMER: customer,
            PARAM_TENANTS: tenants
        }
        return self.__make_request(
            resource=API_TENANT_MAIL_REPORT,
            method=HTTP_POST,
            payload=request
        )

    def application_get(self, application_id=None):
        request = {}
        if application_id:
            request[PARAM_APPLICATION_ID] = application_id

        return self.__make_request(resource=API_APPLICATION,
                                   method=HTTP_GET,
                                   payload=request)

    def application_post(self, customer, description, input_storage,
                         output_storage, host, port, protocol,
                         username, password):
        request = {
            PARAM_CUSTOMER: customer,
            PARAM_DESCRIPTION: description,
            PARAM_INPUT_STORAGE: input_storage,
            PARAM_OUTPUT_STORAGE: output_storage,
            PARAM_CONNECTION: {
                PARAM_HOST: host,
                PARAM_PORT: port,
                PARAM_PROTOCOL: protocol,
                PARAM_USERNAME: username,
                PARAM_PASSWORD: password
            }
        }

        return self.__make_request(resource=API_APPLICATION,
                                   method=HTTP_POST,
                                   payload=request)

    def application_patch(self, application_id, description,
                          input_storage, output_storage,
                          host, port, protocol, username, password):
        request = {
            PARAM_APPLICATION_ID: application_id,
            PARAM_DESCRIPTION: description,
            PARAM_INPUT_STORAGE: input_storage,
            PARAM_OUTPUT_STORAGE: output_storage,
        }
        connection = {
            PARAM_HOST: host,
            PARAM_PORT: port,
            PARAM_PROTOCOL: protocol,
            PARAM_USERNAME: username,
            PARAM_PASSWORD: password
        }
        request = {k: v for k, v in request.items() if v is not None}
        connection = {k: v for k, v in connection.items() if v is not None}
        if connection:
            request[PARAM_CONNECTION] = connection

        return self.__make_request(resource=API_APPLICATION,
                                   method=HTTP_PATCH,
                                   payload=request)

    def application_delete(self, application_id, force=None):
        request = {
            PARAM_APPLICATION_ID: application_id
        }
        if force:
            request[PARAM_FORCE]: force

        return self.__make_request(resource=API_APPLICATION,
                                   method=HTTP_DELETE,
                                   payload=request)

    def application_licenses_get(self, application_id=None):
        request = {}
        if application_id:
            request[PARAM_APPLICATION_ID] = application_id

        return self.__make_request(resource=API_APPLICATION_LICENSES,
                                   method=HTTP_GET,
                                   payload=request)

    def application_licenses_post(self, customer, description, cloud,
                                  tenant_license_key):
        request = {
            PARAM_CUSTOMER: customer,
            PARAM_DESCRIPTION: description,
            PARAM_CLOUD: cloud,
            PARAM_TENANT_LICENSE_KEY: tenant_license_key,
        }

        return self.__make_request(resource=API_APPLICATION_LICENSES,
                                   method=HTTP_POST,
                                   payload=request)

    def application_licenses_delete(self, application_id, force=None):
        request = {
            PARAM_APPLICATION_ID: application_id
        }
        if force:
            request[PARAM_FORCE] = force
        return self.__make_request(resource=API_APPLICATION_LICENSES,
                                   method=HTTP_DELETE,
                                   payload=request)

    def application_dojo_get(self, application_id=None):
        request = {}
        if application_id:
            request[PARAM_APPLICATION_ID] = application_id

        return self.__make_request(resource=API_APPLICATION_DOJO,
                                   method=HTTP_GET,
                                   payload=request)

    def application_dojo_post(self, customer, description, host,
                              port, protocol, stage, api_key):
        request = {
            PARAM_CUSTOMER: customer,
            PARAM_DESCRIPTION: description,
            PARAM_HOST: host,
            PARAM_PORT: port,
            PARAM_PROTOCOL: protocol,
            PARAM_STAGE: stage,
            PARAM_API_KEY: api_key,
        }

        return self.__make_request(resource=API_APPLICATION_DOJO,
                                   method=HTTP_POST,
                                   payload=request)

    def application_dojo_delete(self, application_id, force=None):
        request = {
            PARAM_APPLICATION_ID: application_id
        }
        if force:
            request[PARAM_FORCE] = force
        return self.__make_request(resource=API_APPLICATION_DOJO,
                                   method=HTTP_DELETE,
                                   payload=request)

    def application_policies_get(self, application_id, group_id=None):
        request = {
            PARAM_APPLICATION_ID: application_id
        }
        if group_id:
            request[PARAM_ID] = group_id

        return self.__make_request(resource=API_APPLICATION_POLICIES,
                                   method=HTTP_GET,
                                   payload=request)

    def application_policies_post(self, application_id, group_policy: dict):
        request = {
            PARAM_APPLICATION_ID: application_id,
            **group_policy
        }

        return self.__make_request(resource=API_APPLICATION_POLICIES,
                                   method=HTTP_POST,
                                   payload=request)

    def application_policies_patch(self, application_id, group_policy: dict):
        request = {
            PARAM_APPLICATION_ID: application_id,
            **group_policy
        }

        return self.__make_request(resource=API_APPLICATION_POLICIES,
                                   method=HTTP_PATCH,
                                   payload=request)

    def application_policies_delete(self, application_id, group_id=None):
        request = {
            PARAM_APPLICATION_ID: application_id,
            PARAM_ID: group_id
        }

        return self.__make_request(resource=API_APPLICATION_POLICIES,
                                   method=HTTP_DELETE,
                                   payload=request)

    def parent_insights_resize(self, parent_id, instance_type):
        request = {
            PARAM_PARENT_ID: parent_id,
            PARAM_INSTANCE_TYPE: instance_type
        }

        return self.__make_request(resource=API_PARENT_INSIGHTS_RESIZE,
                                   method=HTTP_GET,
                                   payload=request)

    def parent_licenses_get(self, application_id=None, parent_id=None):
        request = {}
        if application_id:
            request[PARAM_APPLICATION_ID] = application_id
        if parent_id:
            request[PARAM_PARENT_ID] = parent_id

        return self.__make_request(resource=API_PARENT,
                                   method=HTTP_GET,
                                   payload=request)

    def parent_licenses_post(self, application_id, description,
                             tenant, scope):
        request = {
            PARAM_APPLICATION_ID: application_id,
            PARAM_DESCRIPTION: description,
            PARAM_SCOPE: scope
        }
        if tenant:
            request[PARAM_TENANT] = tenant

        return self.__make_request(resource=API_PARENT,
                                   method=HTTP_POST,
                                   payload=request)

    def parent_licenses_delete(self, parent_id, force=None):
        request = {
            PARAM_PARENT_ID: parent_id
        }
        if force:
            request[PARAM_FORCE] = force

        return self.__make_request(resource=API_PARENT,
                                   method=HTTP_DELETE,
                                   payload=request)

    def parent_dojo_get(self, application_id=None, parent_id=None):
        request = {}
        if application_id:
            request[PARAM_APPLICATION_ID] = application_id
        if parent_id:
            request[PARAM_PARENT_ID] = parent_id

        return self.__make_request(resource=API_PARENT_DOJO,
                                   method=HTTP_GET,
                                   payload=request)

    def parent_dojo_post(self, application_id, description,
                         tenant, scope):
        request = {
            PARAM_APPLICATION_ID: application_id,
            PARAM_DESCRIPTION: description,
            PARAM_SCOPE: scope
        }
        if tenant:
            request[PARAM_TENANT] = tenant

        return self.__make_request(resource=API_PARENT_DOJO,
                                   method=HTTP_POST,
                                   payload=request)

    def parent_dojo_delete(self, parent_id, force=None):
        request = {
            PARAM_PARENT_ID: parent_id
        }
        if force:
            request[PARAM_FORCE] = force

        return self.__make_request(resource=API_PARENT_DOJO,
                                   method=HTTP_DELETE,
                                   payload=request)

    def shape_rule_get(self, parent_id=None, rule_id=None):
        request = {}
        if parent_id:
            request[PARAM_PARENT_ID] = parent_id
        if rule_id:
            request[PARAM_ID] = rule_id

        return self.__make_request(resource=API_SHAPE_RULES,
                                   method=HTTP_GET,
                                   payload=request)

    def shape_rule_post(self, parent_id, action, condition, field,
                        value, application_id=None):
        request = {
            PARAM_PARENT_ID: parent_id,
            PARAM_RULE_ACTION: action,
            PARAM_CONDITION: condition,
            PARAM_FIELD: field,
            PARAM_VALUE: value
        }
        if application_id:
            request[PARAM_APPLICATION_ID] = application_id

        return self.__make_request(resource=API_SHAPE_RULES,
                                   method=HTTP_POST,
                                   payload=request)

    def shape_rule_patch(self, rule_id, parent_id=None, application_id=None,
                         action=None, condition=None, field=None, value=None):
        request = {
            PARAM_ID: rule_id,
            PARAM_PARENT_ID: parent_id,
            PARAM_RULE_ACTION: action,
            PARAM_CONDITION: condition,
            PARAM_FIELD: field,
            PARAM_VALUE: value,
            PARAM_APPLICATION_ID: application_id
        }
        request = {k: v for k, v in request.items() if v is not None}

        return self.__make_request(resource=API_SHAPE_RULES,
                                   method=HTTP_PATCH,
                                   payload=request)

    def shape_rule_delete(self, rule_id):
        request = {
            PARAM_ID: rule_id
        }

        return self.__make_request(resource=API_SHAPE_RULES,
                                   method=HTTP_DELETE,
                                   payload=request)

    def shape_rule_dry_run_get(self, parent_id):
        request = {
            PARAM_PARENT_ID: parent_id
        }

        return self.__make_request(resource=API_SHAPE_RULES_DRY_RUN,
                                   method=HTTP_GET,
                                   payload=request)

    def shape_get(self, name=None, cloud=None):
        request = {}
        if name:
            request[PARAM_NAME] = name
        if cloud:
            request[PARAM_CLOUD] = cloud
        return self.__make_request(resource=API_SHAPE,
                                   method=HTTP_GET,
                                   payload=request)

    def shape_post(self, name, cloud, cpu, memory, network_throughtput, iops,
                   family_type, physical_processor, architecture):
        request = {
            PARAM_NAME: name,
            PARAM_CLOUD: cloud,
            PARAM_CPU: cpu,
            PARAM_MEMORY: memory,
            PARAM_NETWORK_THROUGHPUT: network_throughtput,
            PARAM_IOPS: iops,
            PARAM_FAMILY_TYPE: family_type,
            PARAM_PHYSICAL_PROCESSOR: physical_processor,
            PARAM_ARCHITECTURE: architecture
        }

        return self.__make_request(resource=API_SHAPE,
                                   method=HTTP_POST,
                                   payload=request)

    def shape_patch(self, name, cloud, cpu, memory, network_throughtput, iops,
                    family_type, physical_processor, architecture):
        request = {
            PARAM_NAME: name,
            PARAM_CLOUD: cloud,
            PARAM_CPU: cpu,
            PARAM_MEMORY: memory,
            PARAM_NETWORK_THROUGHPUT: network_throughtput,
            PARAM_IOPS: iops,
            PARAM_FAMILY_TYPE: family_type,
            PARAM_PHYSICAL_PROCESSOR: physical_processor,
            PARAM_ARCHITECTURE: architecture
        }
        request = {k: v for k, v in request.items() if v}

        return self.__make_request(resource=API_SHAPE,
                                   method=HTTP_PATCH,
                                   payload=request)

    def shape_delete(self, name):
        request = {
            PARAM_NAME: name
        }
        return self.__make_request(resource=API_SHAPE,
                                   method=HTTP_DELETE,
                                   payload=request)

    def shape_price_get(self, customer, cloud, name, region, os):
        request = {
            PARAM_NAME: name,
            PARAM_CUSTOMER: customer,
            PARAM_CLOUD: cloud,
            PARAM_REGION: region,
            PARAM_OS: os,
            PARAM_CUSTOMER: customer
        }
        request = {k: v for k, v in request.items() if v}
        return self.__make_request(resource=API_SHAPE_PRICE,
                                   method=HTTP_GET,
                                   payload=request)

    def shape_price_post(self, customer, cloud, name, region, os, on_demand):
        request = {
            PARAM_NAME: name,
            PARAM_CLOUD: cloud,
            PARAM_REGION: region,
            PARAM_OS: os,
            PARAM_ON_DEMAND: on_demand,
            PARAM_CUSTOMER: customer
        }

        return self.__make_request(resource=API_SHAPE_PRICE,
                                   method=HTTP_POST,
                                   payload=request)

    def shape_price_patch(self, customer, cloud, name, region, os, on_demand):
        request = {
            PARAM_NAME: name,
            PARAM_CLOUD: cloud,
            PARAM_REGION: region,
            PARAM_OS: os,
            PARAM_ON_DEMAND: on_demand,
            PARAM_CUSTOMER: customer
        }
        if customer:
            request[PARAM_CUSTOMER] = customer
        return self.__make_request(resource=API_SHAPE_PRICE,
                                   method=HTTP_PATCH,
                                   payload=request)

    def shape_price_delete(self, customer, cloud, name, region, os):
        request = {
            PARAM_NAME: name,
            PARAM_CLOUD: cloud,
            PARAM_REGION: region,
            PARAM_OS: os,
            PARAM_CUSTOMER: customer
        }
        if customer:
            request[PARAM_CUSTOMER] = customer
        return self.__make_request(resource=API_SHAPE_PRICE,
                                   method=HTTP_DELETE,
                                   payload=request)

    def health_check_post(self, check_types=None):
        request = {}
        if check_types:
            request[PARAM_TYPES] = check_types
        return self.__make_request(resource=API_HEALTH_CHECK,
                                   method=HTTP_POST,
                                   payload=request)

    def recommendation_get(self, instance_id=None, recommendation_type=None,
                           customer=None, job_id=None):
        request = {
            PARAM_INSTANCE_ID: instance_id,
            PARAM_RECOMMENDATION_TYPE: recommendation_type,
            PARAM_CUSTOMER: customer,
            PARAM_JOB_ID: job_id
        }
        request = {k: v for k, v in request.items() if v is not None}

        return self.__make_request(resource=API_RECOMMENDATION,
                                   method=HTTP_GET,
                                   payload=request)

    def recommendation_patch(self, instance_id, recommendation_type,
                             feedback_status, customer=None):
        request = {
            PARAM_INSTANCE_ID: instance_id,
            PARAM_RECOMMENDATION_TYPE: recommendation_type,
            PARAM_FEEDBACK_STATUS: feedback_status
        }
        if customer:
            request[PARAM_CUSTOMER] = customer

        return self.__make_request(resource=API_RECOMMENDATION,
                                   method=HTTP_PATCH,
                                   payload=request)

    def license_get(self, license_key=None):
        request = {}
        if license_key:
            request[PARAM_LICENSE_KEY] = license_key
        return self.__make_request(
            resource=API_LICENSE, method=HTTP_GET, payload=request
        )

    def license_delete(self, license_key):
        request = {
            PARAM_LICENSE_KEY: license_key
        }
        return self.__make_request(
            resource=API_LICENSE, method=HTTP_DELETE, payload=request
        )

    def license_sync_post(self, license_key=None):
        request = {}
        if license_key:
            request[PARAM_LICENSE_KEY] = license_key
        return self.__make_request(
            resource=API_LICENSE_SYNC, method=HTTP_POST, payload=request
        )

    def lm_config_setting_get(self):
        return self.__make_request(
            resource=API_LM_CONFIG_SETTING, method=HTTP_GET, payload={}
        )

    def lm_config_setting_post(self, host, port, protocol, stage):
        request = {
            PARAM_HOST: host,
            PARAM_PORT: port,
            PARAM_PROTOCOL: protocol,
            PARAM_STAGE: stage
        }
        return self.__make_request(
            resource=API_LM_CONFIG_SETTING,
            method=HTTP_POST,
            payload=request
        )

    def lm_config_setting_delete(self):
        return self.__make_request(
            resource=API_LM_CONFIG_SETTING, method=HTTP_DELETE, payload={}
        )

    def lm_client_setting_get(self, format: str):
        query = {
            PARAM_FORMAT: format
        }
        return self.__make_request(
            resource=API_LM_CLIENT_SETTING,
            method=HTTP_GET, payload=query
        )

    def lm_client_setting_post(
            self, key_id: str, algorithm: str, private_key: str,
            format: str, b64encoded: bool
    ):
        payload = {
            PARAM_KEY_ID: key_id,
            PARAM_ALGORITHM: algorithm,
            PARAM_PRIVATE_KEY: private_key,
            PARAM_FORMAT: format,
            PARAM_B64ENCODED: b64encoded
        }
        return self.__make_request(
            resource=API_LM_CLIENT_SETTING, method=HTTP_POST, payload=payload
        )

    def lm_client_setting_delete(self, key_id: str):
        return self.__make_request(
            resource=API_LM_CLIENT_SETTING, method=HTTP_DELETE, payload={
                PARAM_KEY_ID: key_id
            }
        )
