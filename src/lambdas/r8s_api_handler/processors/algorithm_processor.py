from enum import EnumMeta
from typing import Type

from modular_sdk.services.customer_service import CustomerService
from mongoengine import ValidationError

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params, RESPONSE_FORBIDDEN_CODE
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, ID_ATTR, NAME_ATTR, \
    GET_METHOD, PATCH_METHOD, DELETE_METHOD, \
    REQUIRED_DATA_ATTRS_ATTR, METRIC_ATTRS_ATTR, TIMESTAMP_ATTR, \
    CUSTOMER_ATTR, USER_ID_ATTR, CLOUD_ATTR, CLOUDS, \
    CLUSTERING_SETTINGS_ATTR, RECOMMENDATION_SETTINGS_ATTR, METRIC_FORMAT_ATTR, \
    METRIC_FORMAT_ATTRS, DELIMITER_ATTR, SKIP_INITIAL_SPACE_ATTR, \
    LINE_TERMINATOR_ATTR, QUOTE_CHAR_ATTR, QUOTING_ATTR, ESCAPE_CHAR_ATTR, \
    DOUBLE_QUOTE_ATTR, MAX_CLUSTERS_ATTR, WCSS_KMEANS_INIT_ATTR, \
    WCSS_KMEANS_MAX_ITER_ATTR, KNEE_INTERP_METHOD_ATTR, \
    WCSS_KMEANS_N_INIT_ATTR, KNEE_POLYMONIAL_DEGREE_ATTR, \
    CLUSTERING_SETTINGS_ATTRS, RECORD_STEP_MINUTES_ATTR, MIN_ALLOWED_DAYS_ATTR, \
    MAX_DAYS_ATTR, MIN_ALLOWED_DAYS_SCHEDULE_ATTR, IGNORE_SAVINGS_ATTR, \
    MAX_RECOMMENDED_SHAPES_ATTR, SHAPE_COMPATIBILITY_RULE_ATTR, \
    SHAPE_SORTING_ATTR, USE_PAST_RECOMMENDATIONS_ATTR, USE_INSTANCE_TAGS_ATTR, \
    ANALYSIS_PRICE_ATTR, IGNORE_ACTIONS_ATTR, TARGET_TIMEZONE_NAME_ATTR, \
    THRESHOLDS_ATTR, RECOMMENDATION_SETTINGS_ATTRS, DISCARD_INITIAL_ZEROS_ATTR, \
    FORBID_CHANGE_FAMILY_ATTR, FORBID_CHANGE_SERIES_ATTR, LICENSED_ATTR
from commons.enum import ListEnum
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.algorithm import Algorithm, KMeansInitEnum, InterpMethodEnum, \
    ShapeCompatibilityRule, ShapeSorting
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from services.algorithm_service import AlgorithmService

_LOG = get_logger('r8s-algorithm-processor')


class AlgorithmProcessor(AbstractCommandProcessor):
    def __init__(self, algorithm_service: AlgorithmService,
                 customer_service: CustomerService):
        self.algorithm_service = algorithm_service
        self.customer_service = customer_service
        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'algorithm processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe algorithm event: {event}')

        alg_id = event.get(ID_ATTR)
        name = event.get(NAME_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)

        if alg_id:
            _LOG.debug(f'Describing algorithm by id \'{alg_id}\'')
            algorithms = [self.algorithm_service.get_by_id(object_id=alg_id)]
        elif name:
            _LOG.debug(f'Describing algorithm by name \'{name}\'')
            algorithms = [self.algorithm_service.get_by_name(name=name)]
        else:
            _LOG.debug(f'Describing all algorithms')
            algorithms = self.algorithm_service.list()

        if user_customer != 'admin':
            _LOG.debug(f'Filtering algorithms only from customer '
                       f'\'{user_customer}\'')
            algorithms = [alg for alg in algorithms if
                          alg and alg.customer == user_customer]

        algorithms = [i for i in algorithms if i]
        if not algorithms:
            _LOG.debug(f'No algorithms found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No algorithms found matching given query'
            )

        _LOG.debug(f'Got {len(algorithms)} algorithms to describe.'
                   f' Converting to dto')
        algs_gto = [algorithm.get_dto() for algorithm in algorithms]

        _LOG.debug(f'Response: {algs_gto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=algs_gto
        )

    def post(self, event):
        _LOG.debug(f'Create algorithm event: {event}')
        validate_params(event,
                        (NAME_ATTR, CUSTOMER_ATTR, CLOUD_ATTR,
                         REQUIRED_DATA_ATTRS_ATTR, METRIC_ATTRS_ATTR,
                         TIMESTAMP_ATTR))

        name = event.get(NAME_ATTR)
        if self.algorithm_service.get_by_name(name=name):
            _LOG.debug(f'Algorithm with name \'{name}\' already exists')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm with name \'{name}\' already exists'
            )

        customer = event.get(CUSTOMER_ATTR)
        user_customer = event.get(PARAM_USER_CUSTOMER)
        user_id = event.get(USER_ID_ATTR)
        if user_customer != 'admin' and customer != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'customer \'{customer}\' entities.')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'User \'{user_id}\' is not authorize to affect '
                        f'customer \'{customer}\' entities.'
            )

        customer_obj = self.customer_service.get(name=customer)
        if not customer_obj:
            _LOG.error(f'Customer with name \'{customer}\' does not exist')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Customer with name \'{customer}\' does not exist'
            )

        cloud = event.get(CLOUD_ATTR)
        self._validate_cloud(cloud=cloud)
        cloud = cloud.upper()

        required_data_attrs = event.get(REQUIRED_DATA_ATTRS_ATTR)
        self._validate_list_of_str(attr_name=REQUIRED_DATA_ATTRS_ATTR,
                                   value=required_data_attrs)

        metric_attrs = event.get(METRIC_ATTRS_ATTR)
        self._validate_list_of_str(attr_name=METRIC_ATTRS_ATTR,
                                   value=metric_attrs)

        timestamp_attr = event.get(TIMESTAMP_ATTR)
        self._validate_timestamp_attr(required_data_attrs=required_data_attrs,
                                      timestamp_attr=timestamp_attr)
        algorithm_data = {
            NAME_ATTR: name,
            CUSTOMER_ATTR: customer,
            CLOUD_ATTR: cloud,
            REQUIRED_DATA_ATTRS_ATTR: required_data_attrs,
            METRIC_ATTRS_ATTR: metric_attrs,
            TIMESTAMP_ATTR: timestamp_attr,
            LICENSED_ATTR: False
        }

        _LOG.debug(f'Algorithm data: {algorithm_data}.')
        algorithm = self.algorithm_service.create(algorithm_data)

        try:
            _LOG.debug(f'Saving algorithm')
            self.algorithm_service.save(algorithm=algorithm)
        except ValidationError as e:
            _LOG.error(f'Error occurred while saving algorithm: '
                       f'{str(e)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=e.message
            )

        _LOG.debug(f'Getting algorithm dto')
        algorithm_dto = algorithm.get_dto()

        _LOG.debug(f'Response: {algorithm_dto}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=algorithm_dto
        )

    def patch(self, event):
        _LOG.debug(f'Update algorithm event: {event}')
        validate_params(event, (NAME_ATTR,))
        optional_attrs = (REQUIRED_DATA_ATTRS_ATTR, METRIC_ATTRS_ATTR,
                          TIMESTAMP_ATTR, CLUSTERING_SETTINGS_ATTR,
                          RECOMMENDATION_SETTINGS_ATTR, METRIC_FORMAT_ATTR)
        if not any([event.get(attr) for attr in optional_attrs]):
            _LOG.error(f'At least one of the following attributes must be '
                       f'specified: {optional_attrs}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'At least one of the following attributes must be '
                        f'specified: {optional_attrs}'
            )
        name = event.get(NAME_ATTR)

        _LOG.debug(f'Describing algorithm by name \'{name}\'')
        algorithm: Algorithm = self.algorithm_service.get_by_name(name=name)

        if not algorithm:
            _LOG.debug(f'Algorithm with name \'{name}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Algorithm with name \'{name}\' does not exist.'
            )

        user_customer = event.get(PARAM_USER_CUSTOMER)
        user_id = event.get(USER_ID_ATTR)
        if user_customer != 'admin' and algorithm.customer != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'customer \'{algorithm.customer}\' entities.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Algorithm with name \'{name}\' does not exist.'
            )

        clustering_settings = event.get(CLUSTERING_SETTINGS_ATTR, {})
        clustering_settings = {k: v for k, v in clustering_settings.items()
                               if k in CLUSTERING_SETTINGS_ATTRS}

        recommendation_settings = event.get(RECOMMENDATION_SETTINGS_ATTR, {})
        recommendation_settings = {k: v for k, v
                                   in recommendation_settings.items()
                                   if k in RECOMMENDATION_SETTINGS_ATTRS}
        if algorithm.licensed and (clustering_settings or
                                   recommendation_settings):
            _LOG.error(f'\'{RECOMMENDATION_SETTINGS_ATTR}\' and '
                       f'\'{CLUSTERING_SETTINGS_ATTR}\' are forbidden '
                       f'to update in licensed algorithm')
            return build_response(
                code=RESPONSE_FORBIDDEN_CODE,
                content=f'\'{RECOMMENDATION_SETTINGS_ATTR}\' and '
                        f'\'{CLUSTERING_SETTINGS_ATTR}\' are forbidden '
                        f'to update in licensed algorithm'
            )

        if clustering_settings:
            _LOG.debug(f'Updating algorithm clustering settings')
            self._validate_clustering_settings(
                clustering_settings=clustering_settings)
            self.algorithm_service.update_clustering_settings(
                algorithm=algorithm,
                clustering_settings=clustering_settings
            )

        if recommendation_settings:
            _LOG.debug(f'Updating algorithm recommendation settings')
            self._validate_recommendation_settings(
                recommendation_settings=recommendation_settings)
            self.algorithm_service.update_recommendation_settings(
                algorithm=algorithm,
                recommendation_settings=recommendation_settings
            )

        required_data_attributes = event.get(REQUIRED_DATA_ATTRS_ATTR)
        if required_data_attributes:
            _LOG.debug(f'Updating algorithm \'{REQUIRED_DATA_ATTRS_ATTR}\'')
            self._validate_list_of_str(attr_name=REQUIRED_DATA_ATTRS_ATTR,
                                       value=required_data_attributes)
            algorithm.required_data_attributes = required_data_attributes

        metric_attrs = event.get(METRIC_ATTRS_ATTR)
        if metric_attrs:
            _LOG.debug(f'Updating algorithm \'{METRIC_ATTRS_ATTR}\'')
            self._validate_list_of_str(attr_name=METRIC_ATTRS_ATTR,
                                       value=metric_attrs)
            algorithm.metric_attributes = metric_attrs

        timestamp_attribute = event.get(TIMESTAMP_ATTR)
        if timestamp_attribute:
            _LOG.debug(f'Updating algorithm \'{TIMESTAMP_ATTR}\' to '
                       f'{timestamp_attribute}')
            self._validate_timestamp_attr(
                required_data_attrs=algorithm.required_data_attributes,
                timestamp_attr=timestamp_attribute)
            algorithm.timestamp_attribute = timestamp_attribute

        metric_format = event.get(METRIC_FORMAT_ATTR, {})
        metric_format = {k: v for k, v in metric_format.items()
                         if k in METRIC_FORMAT_ATTRS}
        if metric_format:
            _LOG.debug(f'Updating algorithm metric format settings')
            self._validate_metric_format_settings(metric_format=metric_format)
            self.algorithm_service.update_metric_format_settings(
                algorithm=algorithm, metric_format_settings=metric_format)

        try:
            _LOG.debug(f'Saving updated algorithm')
            self.algorithm_service.save(algorithm=algorithm)
        except ValidationError as e:
            _LOG.error(f'Error occurred while saving updated algorithm: '
                       f'{str(e)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=e.message
            )
        _LOG.debug(f'Describing algorithm dto')
        algorithm_dto = algorithm.get_dto()

        _LOG.debug(f'Response: {algorithm_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=algorithm_dto
        )

    def delete(self, event):
        _LOG.debug(f'Remove algorithm event: {event}')
        alg_id = event.get(ID_ATTR)
        name = event.get(NAME_ATTR)

        if not alg_id and not name:
            _LOG.error(f'Either \'{ID_ATTR}\' or \'{NAME_ATTR}\' must be '
                       f'specified')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Either \'{ID_ATTR}\' or \'{NAME_ATTR}\' must be '
                        f'specified'
            )

        if alg_id:
            _LOG.debug(f'Describing algorithm by id \'{alg_id}\'')
            algorithm = self.algorithm_service.get_by_id(object_id=alg_id)
        else:
            _LOG.debug(f'Describing algorithm by name \'{name}\'')
            algorithm = self.algorithm_service.get_by_name(name=name)

        if not algorithm:
            _LOG.debug(f'No algorithm found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No algorithm found matching given query'
            )

        user_customer = event.get(PARAM_USER_CUSTOMER)
        user_id = event.get(USER_ID_ATTR)
        if user_customer != 'admin' and algorithm.customer != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorize to affect '
                         f'customer \'{algorithm.customer}\' entities.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'No algorithm found matching given query'
            )

        _LOG.debug(f'Deleting algorithm')
        self.algorithm_service.delete(algorithm=algorithm)

        if alg_id:
            message = f'Algorithm with id \'{alg_id}\' has been deleted'
        else:
            message = f'Algorithm with name \'{name}\' has been deleted'
        _LOG.debug(message)
        return build_response(
            code=RESPONSE_OK_CODE,
            content=message
        )

    @staticmethod
    def _validate_list_of_str(attr_name, value):
        if not isinstance(value, list):
            _LOG.error(f'Attr \'{attr_name}\' must be a list.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Attr \'{attr_name}\' must be a list.'
            )
        if not all([isinstance(item, str) for item in value]):
            _LOG.debug(f'All items in \'{attr_name}\' list must be a strings.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'All items in \'{attr_name}\' list must be a strings.'
            )

    @staticmethod
    def _validate_timestamp_attr(required_data_attrs, timestamp_attr):
        if not isinstance(timestamp_attr, str):
            _LOG.error(f'Timestamp attribute must be a string')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Timestamp attribute must be a string'
            )
        if timestamp_attr not in required_data_attrs:
            _LOG.error(f'Specified timestamp attribute \'{timestamp_attr}\' '
                       f'does not exist in required data attributes '
                       f'\'{required_data_attrs}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Specified timestamp attribute \'{timestamp_attr}\' '
                        f'does not exist in required data attributes '
                        f'\'{required_data_attrs}\''
            )

    @staticmethod
    def _validate_type(attr_name, attr_value, required_type=str):
        if not isinstance(attr_value, required_type):
            message = f'\'{attr_name}\' attribute must be a valid ' \
                      f'\'{required_type.__name__}\''
            return message

    def _validate_dict_value_types(self, d: dict, field_type_mapping):
        errors = []
        for key, value in d.items():
            required_type = field_type_mapping.get(key)
            error = self._validate_type(attr_name=key,
                                        attr_value=value,
                                        required_type=required_type)
            if error:
                errors.append(error)
        return errors

    @staticmethod
    def _validate_cloud(cloud):
        if cloud.upper() not in CLOUDS:
            _LOG.error(f'Unsupported cloud specified. Available clouds: '
                       f'{", ".join(CLOUDS)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Unsupported cloud specified. Available clouds: '
                        f'{", ".join(CLOUDS)}'
            )

    def _validate_metric_format_settings(self, metric_format: dict):
        if not metric_format:
            return
        field_type_mapping = {
            DELIMITER_ATTR: str,
            SKIP_INITIAL_SPACE_ATTR: bool,
            LINE_TERMINATOR_ATTR: str,
            QUOTE_CHAR_ATTR: str,
            QUOTING_ATTR: int,
            ESCAPE_CHAR_ATTR: str,
            DOUBLE_QUOTE_ATTR: bool,
        }

        errors = self._validate_dict_value_types(
            d=metric_format,
            field_type_mapping=field_type_mapping)
        if errors:
            _LOG.error(f'{",".join(errors)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'{",".join(errors)}'
            )

    @staticmethod
    def _validate_enum_field(attr_name, value, enum_: Type[ListEnum],
                             optional=True):
        if optional and not value:
            return
        allowed_values = []
        if isinstance(enum_, ListEnum):
            allowed_values = [i.value for i in enum_.list()]
        elif isinstance(enum_, EnumMeta):
            allowed_values = enum_.list()
        if value not in allowed_values:
            return f'Unsupported \'{attr_name}\' specified. Valid values ' \
                   f'are: {", ".join(allowed_values)}'

    def _validate_clustering_settings(self, clustering_settings):
        if not clustering_settings:
            return

        field_type_mapping = {
            MAX_CLUSTERS_ATTR: int,
            WCSS_KMEANS_INIT_ATTR: str,
            WCSS_KMEANS_MAX_ITER_ATTR: int,
            WCSS_KMEANS_N_INIT_ATTR: int,
            KNEE_INTERP_METHOD_ATTR: str,
            KNEE_POLYMONIAL_DEGREE_ATTR: int
        }
        errors = self._validate_dict_value_types(
            d=clustering_settings,
            field_type_mapping=field_type_mapping)

        wcss_kmeans_init = clustering_settings.get(WCSS_KMEANS_INIT_ATTR)
        errors.append(self._validate_enum_field(
            attr_name=WCSS_KMEANS_INIT_ATTR,
            value=wcss_kmeans_init,
            enum_=KMeansInitEnum
        ))

        knee_interp_method = clustering_settings.get(
            KNEE_INTERP_METHOD_ATTR)

        errors.append(self._validate_enum_field(
            attr_name=KNEE_INTERP_METHOD_ATTR,
            value=knee_interp_method,
            enum_=InterpMethodEnum
        ))

        errors = [i for i in errors if i]
        if errors:
            _LOG.error(f'{",".join(errors)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'{",".join(errors)}'
            )

    def _validate_recommendation_settings(self, recommendation_settings):
        if not recommendation_settings:
            return
        field_type_mapping = {
            RECORD_STEP_MINUTES_ATTR: int,
            THRESHOLDS_ATTR: list,
            MIN_ALLOWED_DAYS_ATTR: int,
            MAX_DAYS_ATTR: int,
            MIN_ALLOWED_DAYS_SCHEDULE_ATTR: int,
            IGNORE_SAVINGS_ATTR: bool,
            MAX_RECOMMENDED_SHAPES_ATTR: int,
            SHAPE_COMPATIBILITY_RULE_ATTR: str,
            SHAPE_SORTING_ATTR: str,
            USE_PAST_RECOMMENDATIONS_ATTR: bool,
            USE_INSTANCE_TAGS_ATTR: bool,
            ANALYSIS_PRICE_ATTR: str,
            IGNORE_ACTIONS_ATTR: list,
            TARGET_TIMEZONE_NAME_ATTR: str,
            DISCARD_INITIAL_ZEROS_ATTR: bool,
            FORBID_CHANGE_FAMILY_ATTR: bool,
            FORBID_CHANGE_SERIES_ATTR: bool
        }
        errors = self._validate_dict_value_types(
            d=recommendation_settings,
            field_type_mapping=field_type_mapping)

        thresholds = recommendation_settings.get(THRESHOLDS_ATTR)
        if thresholds is not None:
            if len(thresholds) != 3:
                errors.append(f'Exactly 3 threshold values '
                              f'must be provided')
            if not all([isinstance(i, int) for i in thresholds]):
                errors.append(f'All of the specified threshold values must '
                              f'be a valid integers.')

        compatibility_rule = recommendation_settings.get(
            SHAPE_COMPATIBILITY_RULE_ATTR)
        errors.append(self._validate_enum_field(
            attr_name=SHAPE_COMPATIBILITY_RULE_ATTR,
            value=compatibility_rule,
            enum_=ShapeCompatibilityRule
        ))

        shape_sorting = recommendation_settings.get(SHAPE_SORTING_ATTR)
        errors.append(self._validate_enum_field(
            attr_name=SHAPE_SORTING_ATTR,
            value=shape_sorting,
            enum_=ShapeSorting
        ))

        if TARGET_TIMEZONE_NAME_ATTR in recommendation_settings:
            target_timezone_name = recommendation_settings.get(
                TARGET_TIMEZONE_NAME_ATTR)
            if not target_timezone_name:
                errors.append(f'target_timezone_name can not be empty.')

        errors = [i for i in errors if i]
        if errors:
            _LOG.error(f'{",".join(errors)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'{",".join(errors)}'
            )
