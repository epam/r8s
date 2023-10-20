from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, PARENT_ID_ATTR, CLOUD_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService
from services.shape_rule_filter_service import ShapeRulesFilterService
from services.shape_service import ShapeService

_LOG = get_logger('r8s-shape-rule-dry-run-processor')


class ShapeRuleDryRunProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 shape_service: ShapeService,
                 shape_rules_filter_service: ShapeRulesFilterService,
                 tenant_service: TenantService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.shape_service = shape_service
        self.shape_rules_filter_service = shape_rules_filter_service
        self.tenant_service = tenant_service

        self.method_to_handler = {
            GET_METHOD: self.get
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'shape rule processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Dry run shape rule event: {event}')
        validate_params(event, (PARENT_ID_ATTR,))

        parent, application = self.resolve_parent_application(
            event=event
        )

        _LOG.debug(f'Resolving rules for parent '
                   f'\'{parent.parent_id}\'')
        parent_meta = self.parent_service.get_parent_meta(
            parent=parent)
        shape_rules = self.parent_service.list_shape_rules(
            parent_meta=parent_meta)

        if not shape_rules:
            _LOG.warning(f'Parent \'{parent.parent_id}\' does not '
                         f'have shape rules.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Parent \'{parent.parent_id}\' does not '
                        f'have shape rules.'
            )
        cloud = None
        if parent.tenant_name:
            _LOG.debug(f'Describing tenant {parent.tenant_name}')
            tenant = self.tenant_service.get(tenant_name=parent.tenant_name)
            if not tenant:
                _LOG.debug(f'Tenant {parent.tenant_name} linked to parent '
                           f'{parent.parent_id} does not exist.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Tenant {parent.tenant_name} linked to parent '
                            f'{parent.parent_id} does not exist.'
                )
            cloud = tenant.cloud
        elif parent.cloud:
            cloud = parent.cloud

        if not cloud:
            _LOG.error(f'Parent {parent.parent_id} must have either ALL#CLOUD '
                       f'or SPECIFIC scope.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent {parent.parent_id} must have either ALL#CLOUD '
                        f'or SPECIFIC scope.'
            )

        shapes = self.shape_service.list(cloud=cloud)
        if not shapes:
            _LOG.error(f'No shapes found for cloud \'{cloud}\'')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No shapes found for cloud \'{cloud}\''
            )
        _LOG.debug(f'Applying shape rules to {len(shapes)} shapes')

        filtered_shapes = self.shape_rules_filter_service. \
            get_allowed_instance_types(
            cloud=cloud,
            parent_meta=parent_meta,
            instances_data=shapes
        )
        _LOG.debug(f'Got {len(filtered_shapes)} filtered shapes')

        _LOG.debug(f'Describing shapes dto')
        shape_names = [shape.name for shape in filtered_shapes]
        shape_names.sort()

        response = {
            "cloud": cloud,
            "total_shapes": len(shapes),
            "allowed_for_parent": len(filtered_shapes),
            "shape_names": shape_names
        }
        _LOG.debug(f'Response: \'{response}\'')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=response
        )

    def resolve_parent_application(self, event):
        _LOG.debug(f'Resolving applications')
        applications = self.application_service.resolve_application(
            event=event)

        if not applications:
            _LOG.warning(f'No application found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'No application found matching given query.'
            )
        parent_id = event.get(PARENT_ID_ATTR)

        parent = self.parent_service.get_parent_by_id(
            parent_id=parent_id
        )
        app_ids = [app.application_id for app in applications]
        if not parent or parent.is_deleted or \
                parent.application_id not in app_ids:
            _LOG.error(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )
        target_application = None

        for application in applications:
            if parent.application_id == application.application_id:
                target_application = application
        return parent, target_application
