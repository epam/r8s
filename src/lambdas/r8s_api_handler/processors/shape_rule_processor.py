from typing import Union, List

from modular_sdk.commons.constants import (RIGHTSIZER_LICENSES_TYPE,
                                           ParentType, ApplicationType)
from modular_sdk.models.application import Application
from modular_sdk.models.parent import Parent
from modular_sdk.services.tenant_service import TenantService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import POST_METHOD, GET_METHOD, PATCH_METHOD, \
    DELETE_METHOD, ID_ATTR, RULE_ACTION_ATTR, CONDITION_ATTR, \
    FIELD_ATTR, VALUE_ATTR, ALLOWED_RULE_ACTIONS, \
    ALLOWED_RULE_CONDITIONS, ALLOWED_SHAPE_FIELDS, PARENT_ID_ATTR, \
    CLOUDS, ERROR_NO_APPLICATION_FOUND
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from models.parent_attributes import ShapeRule
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService
from services.rightsizer_parent_service import RightSizerParentService

_LOG = get_logger('r8s-shape-rule-processor')


class ShapeRuleProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService,
                 parent_service: RightSizerParentService,
                 tenant_service: TenantService):
        self.application_service = application_service
        self.parent_service = parent_service
        self.tenant_service = tenant_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

    def process(self, event: dict) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'shape rule processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event: dict):
        _LOG.debug(f'Describe shape rule event: {event}')

        _LOG.debug('Resolving applications')
        applications = self._revolve_application(event=event)

        parent_id = event.get(PARENT_ID_ATTR)
        app_ids = [app.application_id for app in applications]

        parents = []
        if parent_id:
            _LOG.debug(f'Describing parent \'{parent_id}\'')
            parent = self.get_parent(parent_id=parent_id,
                                     application_ids=app_ids)
            if parent:
                self._validate_parent(parent=parent)
                parents.append(parent)
        else:
            _LOG.debug(f'Describing parents from applications: '
                       f'f{", ".join(app_ids)}')
            parents = self.get_parents(application_ids=app_ids)

        if not parents:
            _LOG.error('No parents found matching given query')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No parents found matching given query'
            )

        shape_rules: List[ShapeRule] = []
        for parent in parents:
            _LOG.debug(f'Resolving rules for parent '
                       f'\'{parent.parent_id}\'')
            parent_meta = self.parent_service.get_parent_meta(
                parent=parent)
            parent_rules = self.parent_service.list_shape_rules(
                parent_meta=parent_meta)
            shape_rules.extend(parent_rules)

        rule_id = event.get(ID_ATTR)
        if rule_id:
            _LOG.debug(f'Describing only rule with id \'{rule_id}\'')
            shape_rules = [shape_rule for shape_rule in shape_rules
                           if shape_rule.rule_id == rule_id]

        if not shape_rules:
            _LOG.warning('No shape rules found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No shape rules found matching given query.'
            )
        shape_rule_dto = []
        for shape_rule in shape_rules:
            rule_dto = self.parent_service.get_shape_rule_dto(
                shape_rule=shape_rule)
            shape_rule_dto.append(rule_dto)

        _LOG.debug(f'Response: {shape_rule_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=shape_rule_dto
        )

    def post(self, event: dict):
        _LOG.debug(f'Create shape rule event: {event}')
        validate_params(event, (PARENT_ID_ATTR, RULE_ACTION_ATTR,
                                CONDITION_ATTR,
                                FIELD_ATTR, VALUE_ATTR))

        parent_id = event.get(PARENT_ID_ATTR)
        parent = self.parent_service.get_parent_by_id(
            parent_id=parent_id
        )
        _LOG.debug(f'Validating parent {parent_id}.')
        self._validate_parent(parent=parent)

        _LOG.debug('Resolving application')
        target_application = self._revolve_application(
            event=event,
            linked_parent=parent
        )

        shape_rule = self.parent_service.create_shape_rule(
            action=event.get(RULE_ACTION_ATTR, '').lower(),
            cloud=target_application.meta.cloud.upper(),
            condition=event.get(CONDITION_ATTR, '').lower(),
            field=event.get(FIELD_ATTR, '').lower(),
            value=event.get(VALUE_ATTR, '').lower()
        )
        _LOG.debug(f'Shape rule created: {shape_rule.as_dict()}')

        errors = self._validate(shape_rule=shape_rule)
        if errors:
            _LOG.error(f'Shape rule is invalid: {", ".join(errors)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Shape rule is invalid: {", ".join(errors)}'
            )

        parent_meta = self.parent_service.get_parent_meta(
            parent=parent)
        _LOG.debug(f'Parent \'{parent.parent_id}\' '
                   f'meta extracted')
        self.parent_service.add_shape_rule_to_meta(
            parent_meta=parent_meta,
            shape_rule=shape_rule
        )
        _LOG.debug(f'Shape rule added to parent '
                   f'\'{parent.parent_id}\' meta')
        self.parent_service.set_parent_meta(
            parent=parent,
            meta=parent_meta
        )

        _LOG.debug(f'Updating parent {parent.parent_id} meta')
        self.parent_service.update(
            parent=parent,
            attributes=[Parent.meta],
            updated_by=event.get(PARAM_USER_SUB)
        )
        _LOG.debug(f'Parent \'{parent.parent_id}\' updated')

        shape_rule_dto = self.parent_service.get_shape_rule_dto(
            shape_rule=shape_rule)

        _LOG.debug(f'Response: {shape_rule_dto}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=shape_rule_dto
        )

    def patch(self, event: dict):
        _LOG.debug(f'Update shape rule event: {event}')

        validate_params(event, (PARENT_ID_ATTR, ID_ATTR,))

        parent_id = event.get(PARENT_ID_ATTR)
        rule_id = event.get(ID_ATTR)

        parent = self.parent_service.get_parent_by_id(
            parent_id=parent_id
        )
        self._validate_parent(parent=parent)

        self._revolve_application(event=event, linked_parent=parent)

        parent_meta = self.parent_service.get_parent_meta(
            parent=parent
        )
        _LOG.debug(f'Describing shape rule {rule_id} in parent')
        shape_rule = self.parent_service.get_shape_rule(
            parent_meta=parent_meta,
            rule_id=rule_id
        )
        if not shape_rule:
            _LOG.error(f'Shape rule \'{rule_id}\' does not exist in '
                       f'parent \'{parent_id}\'')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Shape rule \'{rule_id}\' does not exist in '
                        f'parent \'{parent_id}\''
            )
        _LOG.debug(f'Updating rule {rule_id}')
        self.parent_service.update_shape_rule(
            shape_rule=shape_rule,
            action=event.get(RULE_ACTION_ATTR),
            field=event.get(FIELD_ATTR),
            condition=event.get(CONDITION_ATTR),
            value=event.get(VALUE_ATTR)
        )
        _LOG.debug('Shape rule updated')

        errors = self._validate(shape_rule=shape_rule)
        if errors:
            _LOG.error(f'Shape rule is invalid: {", ".join(errors)}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Shape rule is invalid: {", ".join(errors)}'
            )

        self.parent_service.update_shape_rule_in_parent(
            parent_meta=parent_meta,
            shape_rule=shape_rule
        )
        _LOG.debug(f'Updating parent {parent.parent_id} meta')
        self.parent_service.update(
            parent=parent,
            attributes=[Parent.meta],
            updated_by=event.get(PARAM_USER_SUB)
        )
        _LOG.debug(f'Parent \'{parent.parent_id}\' updated')

        shape_rule_dto = self.parent_service.get_shape_rule_dto(
            shape_rule=shape_rule)

        _LOG.debug(f'Response: {shape_rule_dto}')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=shape_rule_dto
        )

    def delete(self, event: dict):
        _LOG.debug(f'Remove shape rule event: {event}')

        validate_params(event, (ID_ATTR,))

        rule_id = event.get(ID_ATTR)

        applications = self._revolve_application(event=event)

        app_ids = [application.application_id for application in applications]
        parents = self.get_parents(application_ids=app_ids)

        if not parents:
            _LOG.warning('No parents found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No parents found matching given query.'
            )

        target_parent = self.get_parent_with_rule(
            parents=parents,
            rule_id=rule_id
        )

        if not target_parent:
            _LOG.warning(f'Shape rule \'{rule_id}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Shape rule \'{rule_id}\' does not exist.'
            )

        _LOG.debug(f'Going to delete rule \'{rule_id}\' from '
                   f'parent \'{target_parent.parent_id}\'')
        parent_meta = self.parent_service.get_parent_meta(
            parent=target_parent)
        self.parent_service.remove_shape_rule_from_meta(
            parent_meta=parent_meta,
            rule_id=rule_id
        )
        _LOG.debug(f'Rule \'{rule_id}\' removed from parent '
                   f'\'{target_parent.parent_id}\'.')
        self.parent_service.set_parent_meta(
            parent=target_parent,
            meta=parent_meta
        )
        _LOG.debug(f'Updating parent {target_parent.parent_id} meta')
        self.parent_service.update(
            parent=target_parent,
            attributes=[Parent.meta],
            updated_by=event.get(PARAM_USER_SUB)
        )
        _LOG.debug(f'Parent \'{target_parent.parent_id}\' updated')

        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Shape rule \'{rule_id}\' was deleted from parent '
                    f'\'{target_parent.parent_id}\''
        )

    @staticmethod
    def _validate(shape_rule: ShapeRule) -> List[str]:
        errors = []

        rule_action = shape_rule.action

        if not rule_action or rule_action.lower() not in ALLOWED_RULE_ACTIONS:
            errors.append(
                f'Unknown rule action \'{rule_action}\' specified. '
                f'Allowed actions: {", ".join(ALLOWED_RULE_ACTIONS)}')

        condition = shape_rule.condition
        if not condition or condition.lower() not in ALLOWED_RULE_CONDITIONS:
            errors.append(
                f'Unknown rule condition \'{rule_action}\' specified. '
                f'Allowed conditions: {", ".join(ALLOWED_RULE_CONDITIONS)}')

        field = shape_rule.field
        if not field or field.lower() not in ALLOWED_SHAPE_FIELDS:
            errors.append(
                f'Unknown rule field \'{rule_action}\' specified. '
                f'Allowed fields: {", ".join(ALLOWED_SHAPE_FIELDS)}')

        cloud = shape_rule.cloud
        if not cloud or cloud.upper() not in CLOUDS:
            errors.append(f'Unsupported rule cloud: {cloud} specified. '
                          f'Allowed clouds: {CLOUDS}')

        return errors

    def get_parent_with_rule(self, parents: List[Parent],
                             rule_id: str) -> Union[Parent, None]:
        # search for application that contains rule with specified id
        for parent in parents:
            parent_meta = self.parent_service.get_parent_meta(
                parent=parent)
            shape_rule = self.parent_service.get_shape_rule(
                parent_meta=parent_meta,
                rule_id=rule_id
            )
            if shape_rule:
                return parent

    def get_parent(self, parent_id, application_ids: List[str]):
        parent = self.parent_service.get_parent_by_id(
            parent_id=parent_id
        )
        if not parent or parent.is_deleted or \
                parent.application_id not in application_ids:
            _LOG.error(f'Parent \'{parent_id}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent \'{parent_id}\' does not exist.'
            )
        return parent

    def get_parents(self, application_ids):
        parents = []
        for application_id in application_ids:
            app_parents = self.parent_service.list_application_parents(
                application_id=application_id,
                only_active=True
            )
            parents.extend(app_parents)
        return parents

    @staticmethod
    def _validate_parent(parent: Parent = None):
        if not parent:
            _LOG.error('No parent found matching given query.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content='No parent found matching given query.'
            )
        if parent.type != RIGHTSIZER_LICENSES_TYPE:
            _LOG.error(f'Parent of \'{RIGHTSIZER_LICENSES_TYPE}\' '
                       f'type required.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Parent of \'{RIGHTSIZER_LICENSES_TYPE}\' '
                        f'type required.'
            )

    def _revolve_application(
            self, event, linked_parent: Parent = None
    ) -> Union[List[Application], Application]:
        applications = self.application_service.resolve_application(
            event=event, type_=ApplicationType.RIGHTSIZER_LICENSES)

        if not applications:
            _LOG.warning(ERROR_NO_APPLICATION_FOUND)
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=ERROR_NO_APPLICATION_FOUND
            )

        if linked_parent:
            target_application = None
            for application in applications:
                if application.application_id == linked_parent.application_id:
                    target_application = application
            if not target_application:
                _LOG.warning(ERROR_NO_APPLICATION_FOUND)
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=ERROR_NO_APPLICATION_FOUND
                )
            return target_application
        return applications
