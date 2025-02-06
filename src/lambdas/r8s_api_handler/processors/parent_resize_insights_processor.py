from commons import RESPONSE_BAD_REQUEST_CODE, validate_params, build_response, RESPONSE_SERVICE_UNAVAILABLE_CODE, \
    RESPONSE_OK_CODE
from commons.constants import GET_METHOD, PARENT_ID_ATTR, CLOUD_ATTR, \
    INSTANCE_TYPE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.algorithm import Algorithm
from services.algorithm_service import AlgorithmService
from services.customer_preferences_service import CustomerPreferencesService
from services.resize_service import ResizeService
from services.rightsizer_parent_service import RightSizerParentService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-parent-resize-insights-processor')


class ParentResizeInsightsProcessor(AbstractCommandProcessor):
    def __init__(self, parent_service: RightSizerParentService,
                 algorithm_service: AlgorithmService,
                 shape_service: ShapeService,
                 customer_preferences_service: CustomerPreferencesService,
                 resize_service: ResizeService):
        self.parent_service = parent_service
        self.algorithm_service = algorithm_service
        self.shape_service = shape_service
        self.customer_preferences_service = customer_preferences_service
        self.resize_service = resize_service

        self.method_to_handler = {
            GET_METHOD: self.get
        }

    def get(self, event):
        validate_params(event, (PARENT_ID_ATTR, INSTANCE_TYPE_ATTR))

        parent_id = event.get(PARENT_ID_ATTR)
        instance_type_name = event.get(INSTANCE_TYPE_ATTR)

        parent = self.parent_service.get_parent_by_id(parent_id=parent_id)
        if not parent:
            _LOG.warning(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )

        parent_meta = self.parent_service.get_parent_meta(parent=parent)
        algorithm_name = parent_meta.algorithm
        if not algorithm_name:
            _LOG.warning(f'Algorithm \'{algorithm_name}\' attr does not '
                         f'specified in parent \'{parent_id}\' meta.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm_name}\' attr does not '
                        f'specified in parent \'{parent_id}\' meta.'
            )
        algorithm: Algorithm = self.algorithm_service.get_by_name(
            name=algorithm_name)
        if not algorithm:
            _LOG.warning(f'Algorithm \'{algorithm_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Algorithm \'{algorithm_name}\' does not exist.'
            )

        current_shape = self.shape_service.get(name=instance_type_name)
        if not current_shape:
            _LOG.warning(f'Shape \'{instance_type_name}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Shape \'{instance_type_name}\' does not exist.'
            )

        cloud = parent_meta.cloud
        if not cloud:
            _LOG.warning(f'Cloud attr does not specified in '
                         f'parent \'{parent_id}\' meta')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Cloud attr does not specified in '
                        f'parent \'{parent_id}\' meta'
            )

        _LOG.debug(f'Querying cloud \'{cloud}\' shapes')
        shapes = self.shape_service.list(cloud=cloud)
        _LOG.debug(f'Total shapes available for cloud: {len(shapes)}')
        if not shapes:
            _LOG.error(f'Shape for cloud \'{cloud}\' is missing. '
                       f'Please contact the support team')
            return build_response(
                code=RESPONSE_SERVICE_UNAVAILABLE_CODE,
                content=f'Shape for cloud \'{cloud}\' is missing. '
                        f'Please contact the support team'
            )
        allowed_instances, filter_allowed_mapping, filter_excluded_mapping = \
            self.customer_preferences_service.get_allowed_instance_types(
                parent_meta=parent_meta, instances_data=shapes)
        _LOG.debug(f'Shapes allowed by shape rules: {len(allowed_instances)}')
        forbid_change_series = algorithm.recommendation_settings. \
            forbid_change_series
        forbid_change_family = algorithm.recommendation_settings. \
            forbid_change_family
        response = {
            PARENT_ID_ATTR: parent_id,
            CLOUD_ATTR: cloud,
            'total_shapes_available': len(shapes),
            "shape_rules": {
                "left_after_allowed_filters": filter_allowed_mapping,
                "discarded_by_deny_filter": filter_excluded_mapping,
                "total_shapes_fit": len(allowed_instances)
            },
            "algorithm_settings": {
                "forbid_change_series": forbid_change_series,
                "forbid_change_family": forbid_change_family
            },
        }
        if forbid_change_family:
            _LOG.debug(f'Counting shape that will be excluded by family')
            same_family_shapes = self.resize_service.get_same_family(
                sizes=allowed_instances,
                current_shape=current_shape,
                cloud=cloud,
                exclude_shapes=[]
            )
            excluded_by_family = len(allowed_instances) - len(
                same_family_shapes)
            response['algorithm_settings']['excluded_by_family'] = \
                excluded_by_family
            allowed_instances = same_family_shapes
            _LOG.debug(f'Excluded by family: {excluded_by_family}')

        if forbid_change_series:
            _LOG.debug(f'Counting shape that will be excluded by series')
            series_prefix = self.resize_service.get_series_prefix(
                shape_name=instance_type_name,
                cloud=cloud
            )
            same_series_shapes = self.resize_service.get_same_series(
                sizes=allowed_instances,
                series_prefix=series_prefix
            )
            excluded_by_series = len(allowed_instances) - len(
                same_series_shapes)
            response['algorithm_settings'][
                'excluded_by_series'] = excluded_by_series
            _LOG.debug(f'Excluded by series: {excluded_by_series}')
            allowed_instances = same_series_shapes

        _LOG.debug(f'Result available shapes count: {len(allowed_instances)}')
        response['available_shapes'] = len(allowed_instances)
        _LOG.debug(f'Response: {response}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )
