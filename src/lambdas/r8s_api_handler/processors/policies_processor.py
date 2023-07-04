from commons import RESPONSE_BAD_REQUEST_CODE, raise_error_response, \
    build_response, RESPONSE_RESOURCE_NOT_FOUND_CODE, RESPONSE_OK_CODE, \
    validate_params
from commons.abstract_lambda import PARAM_HTTP_METHOD
from commons.constants import GET_METHOD, POST_METHOD, DELETE_METHOD, \
    PATCH_METHOD, NAME_ATTR, PERMISSIONS_ATTR, \
    PERMISSIONS_ADMIN_ATTR, PERMISSIONS_TO_ATTACH, PERMISSIONS_TO_DETACH
from commons.log_helper import get_logger
from lambdas.r8s_api_handler.processors.abstract_processor import \
    AbstractCommandProcessor
from services.rbac.access_control_service import AccessControlService
from services.rbac.iam_service import IamService
from services.user_service import CognitoUserService

_LOG = get_logger('r8s-policy-processor')


class PolicyProcessor(AbstractCommandProcessor):
    def __init__(self, user_service: CognitoUserService,
                 access_control_service: AccessControlService,
                 iam_service: IamService):
        self.user_service = user_service
        self.access_control_service = access_control_service
        self.iam_service = iam_service
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
                      f'policy processor'
            _LOG.error(f'status code: {RESPONSE_BAD_REQUEST_CODE}, '
                       f'process error: {message}')
            raise_error_response(message, RESPONSE_BAD_REQUEST_CODE)
        return command_handler(event=event)

    def get(self, event):
        _LOG.debug(f'Get policy event: {event}')
        policy_name = event.get(NAME_ATTR)
        if policy_name:
            _LOG.debug(f'Extracting policy with name \'{policy_name}\'')
            policies = [self.iam_service.policy_get(policy_name=policy_name)]
        else:
            _LOG.debug(f'Extracting all available policies')
            policies = self.iam_service.list_policies()

        if not policies or policies \
                and all([policy is None for policy in policies]):
            _LOG.debug('No policies found matching given query.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content='No policies found matching given query.'
            )

        policies_dto = [policy.get_dto() for policy in policies]
        _LOG.debug(f'Policies to return: {policies_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=policies_dto
        )

    def post(self, event):
        _LOG.debug(f'Create policy event: {event}')
        validate_params(event, (NAME_ATTR,))

        if not event.get(PERMISSIONS_ATTR) \
                and not event.get(PERMISSIONS_ADMIN_ATTR):
            required = ", ".join((PERMISSIONS_ATTR, PERMISSIONS_ADMIN_ATTR))
            _LOG.debug(f'One of the attributes \'{required}\' must be '
                       f'specified')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'One of the attributes \'{required}\' must be '
                        f'specified'
            )
        policy_name = event.get(NAME_ATTR)

        if self.access_control_service.policy_exists(name=policy_name):
            _LOG.debug(f'Policy with name \'{policy_name}\' already exists.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'Policy with name \'{policy_name}\' already exists.'
            )

        permissions = event.get(PERMISSIONS_ATTR)
        if permissions:
            non_existing = self.access_control_service. \
                get_non_existing_permissions(permissions=permissions)

            if non_existing:
                _LOG.debug(f'Some of the specified permissions don\'t exist: '
                           f'{", ".join(non_existing)}')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Some of the specified permissions don\'t exist: '
                            f'{", ".join(non_existing)}'
                )
        elif event.get(PERMISSIONS_ADMIN_ATTR, None):
            permissions = self.access_control_service.get_admin_permissions()

        policy_data = {
            NAME_ATTR: policy_name,
            PERMISSIONS_ATTR: permissions
        }
        _LOG.debug(f'Going to create policy with data: {policy_data}')
        policy = self.access_control_service.create_policy(
            policy_data=policy_data)

        _LOG.debug(f'Saving policy')
        self.access_control_service.save(policy)

        policy_dto = policy.get_dto()
        _LOG.debug(f'Response: {policy_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=policy_dto
        )

    def patch(self, event):
        _LOG.debug(f'Update policy event: {event}')
        validate_params(event, (NAME_ATTR,))

        policy_name = event.get(NAME_ATTR)
        permissions = event.get(PERMISSIONS_ATTR)
        to_attach = event.get(PERMISSIONS_TO_ATTACH)
        to_detach = event.get(PERMISSIONS_TO_DETACH)

        if not any(i for i in (permissions, to_attach, to_detach)):
            required = ', '.join((PERMISSIONS_ATTR, PERMISSIONS_TO_ATTACH,
                                  PERMISSIONS_TO_DETACH))
            _LOG.debug(f'One of the following arguments \'{required}\' must '
                       f'be provided.')
            return build_response(
                code=RESPONSE_BAD_REQUEST_CODE,
                content=f'One of the following arguments \'{required}\' must '
                        f'be provided.'
            )
        if not self.access_control_service.policy_exists(name=policy_name):
            _LOG.debug(f'Policy with name \'{policy_name}\' does not exist.')
            return build_response(
                code=RESPONSE_RESOURCE_NOT_FOUND_CODE,
                content=f'Policy with name \'{policy_name}\' does not exist.'
            )
        policy = self.access_control_service.get_policy(name=policy_name)
        if permissions:
            _LOG.debug(f'Going to reset permissions for policy with name '
                       f'\'{policy_name}\'. Permissions: {permissions}')
            non_existing = self.access_control_service. \
                get_non_existing_permissions(permissions=permissions)

            if non_existing:
                _LOG.debug(f'Some of the specified permissions don\'t exist: '
                           f'{", ".join(non_existing)}')
                return build_response(
                    code=RESPONSE_BAD_REQUEST_CODE,
                    content=f'Some of the specified permissions don\'t exist: '
                            f'{", ".join(non_existing)}'
                )
            policy.permissions = permissions
        else:
            if to_attach:
                _LOG.debug(f'going to attach permissions to policy: '
                           f'\'{to_attach}\'')
                non_existing = self.access_control_service.\
                    get_non_existing_permissions(permissions=to_attach)

                if non_existing:
                    _LOG.debug(
                        f'Some of the specified permissions don\'t exist: '
                        f'{", ".join(non_existing)}')
                    return build_response(
                        code=RESPONSE_BAD_REQUEST_CODE,
                        content=f'Some of the specified permissions don\'t '
                                f'exist: {", ".join(non_existing)}'
                    )
                policy_permissions = policy.get_json().get(PERMISSIONS_ATTR)
                policy_permissions.extend(to_attach)
                policy_permissions = list(set(policy_permissions))
                policy.permissions = policy_permissions
            if to_detach:
                _LOG.debug(f'going to detach permissions from policy: '
                           f'\'{to_detach}\'')
                policy_permissions = policy.get_json().get(PERMISSIONS_ATTR)
                for permission in to_detach:
                    if permission in policy_permissions:
                        _LOG.debug(f'Removing permission: {permission}')
                        policy_permissions.remove(permission)
                    else:
                        _LOG.debug(f'Permission \'{permission}\' does not '
                                   f'exist in policy.')
                policy.permissions = policy_permissions
        _LOG.debug(f'Saving policy')
        self.access_control_service.save(policy)

        policy_dto = policy.get_dto()
        _LOG.debug(f'Response: {policy_dto}')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=policy_dto
        )

    def delete(self, event):
        _LOG.debug(f'Delete policy event: {event}')
        validate_params(event, (NAME_ATTR,))

        policy_name = event.get(NAME_ATTR)
        if not self.access_control_service.policy_exists(name=policy_name):
            _LOG.debug(f'Policy with name \'{policy_name}\' does not exist.')
            return build_response(
                code=RESPONSE_OK_CODE,
                content=f'Policy with name \'{policy_name}\' does not exist.'
            )
        _LOG.debug(f'Extracting policy with name \'{policy_name}\'')
        policy = self.access_control_service.get_policy(name=policy_name)
        _LOG.debug(f'Deleting policy')
        self.access_control_service.delete_entity(policy)
        _LOG.debug(f'Policy with name \'{policy_name}\' has been deleted.')
        return build_response(
            code=RESPONSE_OK_CODE,
            content=f'Policy with name \'{policy_name}\' has been deleted.'
        )
