from datetime import datetime

from modular_sdk.services.customer_service import CustomerService

from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, PATCH_METHOD, \
    DELETE_METHOD, NAME_ATTR, EXPIRATION_ATTR, POLICIES_ATTR, \
    POLICIES_TO_ATTACH, POLICIES_TO_DETACH, RESOURCE_ATTR
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rbac.access_control_service import AccessControlService
from services.rbac.iam_service import IamService
from services.user_service import CognitoUserService

_LOG = get_logger('r8s-role-processor')


class RoleProcessor(AbstractCommandProcessor):
    def __init__(self, user_service: CognitoUserService,
                 access_control_service: AccessControlService,
                 iam_service: IamService, customer_service: CustomerService):
        self.user_service = user_service
        self.access_control_service = access_control_service
        self.iam_service = iam_service
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
                      f'role processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Get role event: {event}')
        role_name = event.get(NAME_ATTR)
        if role_name:
            _LOG.debug(f'Extracting role with name \'{role_name}\'')
            roles = [self.iam_service.role_get(role_name=role_name)]
        else:
            _LOG.debug('Extracting all available roles')
            roles = self.iam_service.list_roles()

        if not roles:
            _LOG.debug('No roles found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No roles found matching given query.'
            )

        roles_dto = [role.get_dto() for role in roles]
        _LOG.debug(f'Roles to return: {roles_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=roles_dto
        )

    def post(self, event):
        _LOG.debug(f'Create role event: {event}')
        validate_params(event, (NAME_ATTR, EXPIRATION_ATTR, POLICIES_ATTR))

        expiration = event.get(EXPIRATION_ATTR)
        error = self._validate_expiration(value=expiration)
        if error:
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=error
            )

        role_name = event.get(NAME_ATTR)
        policies = event.get(POLICIES_ATTR)

        if not isinstance(policies, list) and \
                not all([isinstance(i, str) for i in policies]):
            _LOG.error(f'\'{POLICIES_ATTR}\' attribute must be a list of '
                       f'strings.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'\'{POLICIES_ATTR}\' attribute must be a list of '
                        f'strings.'
            )

        if self.access_control_service.role_exists(name=role_name):
            _LOG.error(f'Role with name \'{role_name}\' already exists.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Role with name \'{role_name}\' already exists.'
            )

        non_existing_policies = self.access_control_service. \
            get_non_existing_policies(policies=policies)
        if non_existing_policies:
            error_message = f'Some of the policies provided in the event ' \
                            f'don\'t exist: {", ".join(non_existing_policies)}'
            _LOG.error(error_message)
            return build_response(code=RESPONSE_BAD_REQUEST_CODE,
                                  content=error_message)

        resource = event.get(RESOURCE_ATTR)

        if resource and not self.customer_service.get(name=resource):
            _LOG.warning(f'Customer with name \'{resource}\' does not exist.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Customer with name \'{resource}\' does not exist.'
            )

        role_data = {
            NAME_ATTR: role_name,
            EXPIRATION_ATTR: expiration,
            POLICIES_ATTR: policies
        }
        if resource:
            role_data[RESOURCE_ATTR]: resource

        _LOG.debug(f'Creating role from data: {role_data}')
        role = self.access_control_service.create_role(role_data=role_data)
        _LOG.debug('Role has been created. Saving.')
        self.access_control_service.save(role)

        _LOG.debug('Extracting role dto')
        role_dto = role.get_dto()
        _LOG.debug(f'Response: {role_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=role_dto
        )

    def patch(self, event):
        _LOG.debug(f'Patch role event" {event}')
        validate_params(event, (NAME_ATTR,))

        role_name = event.get(NAME_ATTR)
        if not self.access_control_service.role_exists(name=role_name):
            _LOG.error(f'Role with name \'{role_name}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Role with name \'{role_name}\' does not exist.'
            )

        _LOG.debug(f'Extracting role with name \'{role_name}\'')
        role = self.access_control_service.get_role(name=role_name)

        expiration = event.get(EXPIRATION_ATTR)
        if expiration:
            error = self._validate_expiration(expiration)
            if error:
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=error
                )
            _LOG.debug(f'Setting role expiration to \'{expiration}\'')
            role.expiration = expiration

        to_attach = event.get(POLICIES_TO_ATTACH)
        if to_attach:
            _LOG.debug(f'Attaching policies \'{to_attach}\'')
            non_existing = self.access_control_service. \
                get_non_existing_policies(policies=to_attach)
            if non_existing:
                _LOG.error(f'Some of the policies provided in the request '
                           f'do not exist: \'{non_existing}\'')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Some of the policies provided in the request '
                            f'do not exist: \'{", ".join(non_existing)}\''
                )
            role_policies = role.get_json().get(POLICIES_ATTR)
            role_policies.extend(to_attach)
            role_policies = list(set(role_policies))
            _LOG.debug(f'Role policies: {role_policies}')
            role.policies = role_policies
        to_detach = event.get(POLICIES_TO_DETACH)
        if to_detach:
            _LOG.debug(f'Detaching policies \'{to_detach}\'')
            role_policies = role.get_json().get(POLICIES_ATTR)
            for policy in to_detach:
                if policy in role_policies:
                    role_policies.remove(policy)
                else:
                    _LOG.error(f'Policy \'{to_detach}\' does not exist in '
                               f'role \'{role_name}\'.')
            _LOG.debug(f'Setting role policies: {role_policies}')
            role.policies = role_policies

        _LOG.debug('Saving role')
        self.access_control_service.save(role)

        _LOG.debug('Extracting role dto')
        role_dto = role.get_dto()

        _LOG.debug(f'Response: {role_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=role_dto
        )

    def delete(self, event):
        _LOG.debug(f'Delete role event: {event}')
        validate_params(event, (NAME_ATTR,))

        role_name = event.get(NAME_ATTR)
        if not self.access_control_service.role_exists(name=role_name):
            _LOG.debug(f'Role with name \'{role_name}\' does not exist.')
            return build_response(
                code=RESPONSE_OK_CODE,
                content=f'Role with name \'{role_name}\' does not exist.'
            )
        _LOG.debug(f'Extracting role with name \'{role_name}\'')
        role = self.access_control_service.get_role(name=role_name)

        _LOG.debug('Deleting role')
        self.access_control_service.delete_entity(role)
        _LOG.debug(f'Role with name \'{role_name}\' has been deleted.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Role with name \'{role_name}\' has been deleted.'
        )

    @staticmethod
    def _validate_expiration(value):
        try:
            expiration = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            _LOG.debug(
                f'Provided \'{EXPIRATION_ATTR}\' does not match the iso '
                f'format.')
            return f'Provided \'{EXPIRATION_ATTR}\' does not match the ' \
                   f'ISO format.'

        now = datetime.now()
        if now > expiration:
            _LOG.debug('Provided expiration date has already passed.')
            return 'Provided expiration date has already passed.'
