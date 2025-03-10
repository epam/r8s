from commons import (RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
                     build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE,
                     RESPONSE_OK_CODE,
                     validate_params, generate_id)
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, PATCH_METHOD, \
    DELETE_METHOD, MAESTRO_RIGHTSIZER_APPLICATION_TYPE, ID_ATTR, \
    APPLICATION_ID_ATTR, ERROR_NO_APPLICATION_FOUND, NAME_ATTR, TAG_ATTR, \
    TYPE_ATTR, GROUP_POLICY_AUTO_SCALING, SCALE_STEP_ATTR, \
    SCALE_STEP_AUTO_DETECT, COOLDOWN_DAYS_ATTR, THRESHOLDS_ATTR, MIN_ATTR, \
    MAX_ATTR, DESIRED_ATTR
from commons.log_helper import get_logger

from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rbac.access_control_service import PARAM_USER_SUB
from services.rightsizer_application_service import \
    RightSizerApplicationService

from modular_sdk.models.application import Application

_LOG = get_logger('r8s-group-policy-processor')

DEFAULT_COOLDOWN_DAYS = 7
THRESHOLD_KEYS = (MIN_ATTR, MAX_ATTR, DESIRED_ATTR)


class GroupPolicyProcessor(AbstractCommandProcessor):
    def __init__(self, application_service: RightSizerApplicationService):
        self.application_service = application_service

        self.method_to_handler = {
            GET_METHOD: self.get,
            POST_METHOD: self.post,
            PATCH_METHOD: self.patch,
            DELETE_METHOD: self.delete,
        }

        self.type_builder = {
            GROUP_POLICY_AUTO_SCALING: self._build_autoscaling
        }

    def process(self, event) -> dict:
        method = event.get(PARAM_HTTP_METHOD)
        command_handler = self.method_to_handler.get(method)
        if not command_handler:
            message = f'Unable to handle command {method} in ' \
                      f'grop policy processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Describe group policy event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR,))

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
        )

        if not applications:
            _LOG.warning(ERROR_NO_APPLICATION_FOUND)
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=ERROR_NO_APPLICATION_FOUND
            )
        application: Application = applications[0]

        _LOG.debug(f'Describing application {application.application_id} meta')
        meta = self.application_service.get_application_meta(
            application=application
        )

        group_id = event.get(ID_ATTR)

        groups = []
        if group_id:
            _LOG.debug(f'Describing group {group_id}')
            group = self.application_service.get_group_policy(
                meta=meta,
                group_id=group_id)
            if group:
                groups.append(group)
        else:
            _LOG.debug(f'Listing application {application.application_id} '
                       f'groups')
            groups = self.application_service.list_group_policies(meta=meta)

        if not groups:
            _LOG.debug('No policy groups found matching given query')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No policy groups found matching given query'
            )

        _LOG.debug(f'Response: {groups}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=groups
        )

    def post(self, event):
        _LOG.debug(f'Create group policy event: {event}')
        validate_params(event,
                        (APPLICATION_ID_ATTR, TYPE_ATTR, TAG_ATTR))

        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
        )
        if not applications:
            _LOG.warning(ERROR_NO_APPLICATION_FOUND)
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=ERROR_NO_APPLICATION_FOUND
            )
        application: Application = applications[0]

        policy_type = event.get(TYPE_ATTR)

        builder_func = self.type_builder.get(policy_type)
        if not builder_func:
            _LOG.error(f'Invalid policy type specified: {policy_type}. '
                       f'Available policy types:'
                       f' {list(self.type_builder.keys())}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid policy type specified: {policy_type}. '
                        f'Available policy types:'
                        f' {list(self.type_builder.keys())}'
            )
        _LOG.debug(f'Building {policy_type} group policy')
        group_policy = builder_func(event=event)
        _LOG.debug(f'Group policy content: {group_policy}. Adding to '
                   f'application {application.application_id} meta')

        meta = self.application_service.get_application_meta(
            application=application
        )

        self.application_service.add_group_policy_to_meta(
            meta=meta,
            group_policy=group_policy
        )

        _LOG.debug(f'Saving updated application {application.application_id}')
        application.meta = meta
        self.application_service.update_meta(
            application=application,
            updated_by=event.get(PARAM_USER_SUB)
        )

        _LOG.debug(f'Response: {group_policy}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=group_policy
        )

    def patch(self, event):
        _LOG.debug(f'Update group policy event: {event}')
        validate_params(event, (APPLICATION_ID_ATTR, ID_ATTR))
        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
        )
        if not applications:
            _LOG.warning(ERROR_NO_APPLICATION_FOUND)
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=ERROR_NO_APPLICATION_FOUND
            )
        application: Application = applications[0]

        group_id = event.get(ID_ATTR)
        _LOG.debug(f'Describing application {application.application_id} meta')
        meta = self.application_service.get_application_meta(
            application=application
        )

        _LOG.debug(f'Describing group {group_id} from application '
                   f'{application.application_id}')
        group_policy = self.application_service.get_group_policy(meta=meta,
                                                                 group_id=group_id)
        if not group_policy:
            _LOG.debug(f'Group {group_id} does not exist in application '
                       f'{application.application_id}')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Group {group_id} does not exist in application '
                        f'{application.application_id}'
            )

        policy_type = group_policy.get(TYPE_ATTR)

        builder_func = self.type_builder.get(policy_type)
        if not builder_func:
            _LOG.error(f'Invalid policy type specified: {policy_type}. '
                       f'Available policy types:'
                       f' {list(self.type_builder.keys())}')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Invalid policy type specified: {policy_type}. '
                        f'Available policy types:'
                        f' {list(self.type_builder.keys())}'
            )
        _LOG.debug(f'Updating {policy_type} group policy')

        group_policy = builder_func(event=event, group_policy=group_policy)

        _LOG.debug(f'Group policy content: {group_policy}. Updating in '
                   f'application {application.application_id} meta')
        self.application_service.update_group_policy_in_meta(
            meta=meta,
            group_policy=group_policy
        )
        application.meta = meta
        _LOG.debug(f'Saving updated application {application.application_id}')

        self.application_service.update_meta(
            application=application,
            updated_by=event.get(PARAM_USER_SUB)
        )
        _LOG.debug(f'Response: {group_policy}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=group_policy
        )

    def delete(self, event):
        _LOG.debug(f'Delete group policy event: {event}')

        validate_params(event, (APPLICATION_ID_ATTR, ID_ATTR))
        _LOG.debug('Resolving applications')
        applications = self.application_service.resolve_application(
            event=event, type_=MAESTRO_RIGHTSIZER_APPLICATION_TYPE
        )
        if not applications:
            _LOG.warning(ERROR_NO_APPLICATION_FOUND)
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=ERROR_NO_APPLICATION_FOUND
            )
        application: Application = applications[0]

        group_id = event.get(ID_ATTR)
        updated_by = event.get(PARAM_USER_SUB)

        _LOG.debug(f'Describing application {application.application_id} meta')
        meta = self.application_service.get_application_meta(
            application=application
        )

        _LOG.debug(f'Describing group {group_id} from application '
                   f'{application.application_id}')
        group = self.application_service.get_group_policy(meta=meta,
                                                          group_id=group_id)
        if not group:
            _LOG.debug(f'Group {group_id} does not exist in application '
                       f'{application.application_id}')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Group {group_id} does not exist in application '
                        f'{application.application_id}'
            )

        _LOG.debug(f'Removing group {group_id} from application '
                   f'{application.application_id}')
        self.application_service.remove_group_from_meta(
            meta=meta,
            group_id=group_id
        )
        application.meta = meta

        _LOG.debug('Saving updated application')
        self.application_service.update_meta(
            application=application,
            updated_by=updated_by
        )

        _LOG.debug(f'Group policy {group_id} has been removed from '
                   f'application {application.application_id}.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Group policy {group_id} has been removed from '
                    f'application {application.application_id}.'
        )

    def _build_autoscaling(self, event, group_policy: dict = None):
        if not group_policy:
            group_policy = {
                ID_ATTR: generate_id(),
                TYPE_ATTR: GROUP_POLICY_AUTO_SCALING,
                TAG_ATTR: event.get(TAG_ATTR),
                SCALE_STEP_ATTR: SCALE_STEP_AUTO_DETECT,
                COOLDOWN_DAYS_ATTR: DEFAULT_COOLDOWN_DAYS
            }

        scale_step = event.get(SCALE_STEP_ATTR)
        if scale_step:
            _LOG.debug(f'Validating scale_step: {scale_step}')
            if scale_step == SCALE_STEP_AUTO_DETECT:
                group_policy[SCALE_STEP_ATTR] = SCALE_STEP_AUTO_DETECT
            else:
                self._validate_positive_int(key=SCALE_STEP_ATTR,
                                            value=scale_step)
                group_policy[SCALE_STEP_ATTR] = scale_step

        cooldown_days = event.get(COOLDOWN_DAYS_ATTR)
        if cooldown_days:
            _LOG.debug(f'Validating cooldown days: {cooldown_days}')
            self._validate_positive_int(key=COOLDOWN_DAYS_ATTR,
                                        value=cooldown_days)
            group_policy[COOLDOWN_DAYS_ATTR] = cooldown_days

        thresholds = event.get(THRESHOLDS_ATTR)
        if thresholds:
            _LOG.debug(f'Validating thresholds: {thresholds}')
            if not isinstance(thresholds, dict):
                _LOG.error(f'\'{THRESHOLD_KEYS}\' attr must be a valid dict.')
            if not all(key in thresholds for key in THRESHOLD_KEYS):
                _LOG.error(f'All {", ".join(THRESHOLD_KEYS)} '
                           f'must be specified.')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'All {", ".join(THRESHOLD_KEYS)} '
                            f'must be specified.'
                )
            for key in THRESHOLD_KEYS:
                value = thresholds.get(key)
                self._validate_positive_int(key=f'{THRESHOLDS_ATTR}.{key}',
                                            value=value)
            if not thresholds[MIN_ATTR] < thresholds[DESIRED_ATTR] < \
                   thresholds[MAX_ATTR]:
                _LOG.error(f'Invalid thresholds specified. Thresholds must '
                           f'be in increasing order {MIN_ATTR} < '
                           f'{DESIRED_ATTR} < {MAX_ATTR}')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Invalid thresholds specified. Thresholds must '
                            f'be in increasing order {MIN_ATTR} < '
                            f'{DESIRED_ATTR} < {MAX_ATTR}'
                )
            group_policy[THRESHOLDS_ATTR] = {
                MIN_ATTR: thresholds.get(MIN_ATTR),
                DESIRED_ATTR: thresholds.get(DESIRED_ATTR),
                MAX_ATTR: thresholds.get(MAX_ATTR)
            }

        tag = event.get(TAG_ATTR)
        if tag:
            group_policy[TAG_ATTR] = tag

        return group_policy

    @staticmethod
    def _validate_positive_int(key: str, value):
        if not isinstance(value, int) or value < 1:
            _LOG.error(f'\'{key}\' attr must '
                       f'be a valid positive int')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{key}\' attr must '
                        f'be a valid positive int'
            )
