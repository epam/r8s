from datetime import datetime, timedelta
from typing import Union

from commons.constants import USER_ID_ATTR, CUSTOMER_ATTR, \
    TENANT_SCOPED_PERMISSION_GROUPS, PARAM_USER_TENANT_ACCESS
from commons.log_helper import get_logger
from models.policy import Policy
from models.role import Role
from services.rbac.iam_service import IamService
from services.rbac.tenant_access import PolicyStruct, TenantAccess
from services.setting_service import SettingsService
from services.user_service import CognitoUserService

_LOG = get_logger('access-control-service')

PARAM_NAME = 'name'
PARAM_PERMISSIONS = 'permissions'
PARAM_EXPIRATION = 'expiration'
PARAM_REQUEST_PATH = 'request_path'
PARAM_TARGET_USER = 'target_user'
PARAM_USER_CUSTOMER = 'user_customer'
PARAM_USER_SUB = 'user_sub'


class AccessControlService:

    def __init__(self, iam_service: IamService,
                 user_service: CognitoUserService,
                 setting_service: SettingsService):
        self.iam_service = iam_service
        self.user_service = user_service
        self.setting_service = setting_service

    def is_allowed_to_access(self, event: dict,
                             target_permission: str) -> bool:

        user_id = event.get(USER_ID_ATTR)
        _LOG.debug(f'Searching for user with id: {user_id}')
        if not self.user_service.is_user_exists(username=user_id):
            _LOG.warning(f'User with id: {user_id} does not exist')
            return False

        _LOG.debug(f'Checking permissions of user {user_id} '
                   f'on \'{target_permission}\' action')
        role_names = self.user_service.get_user_roles(user=user_id)
        user_customer = self.user_service.get_user_customer(user=user_id)
        user_sub = self.user_service.get_user_id(user=user_id)
        event[PARAM_USER_CUSTOMER] = user_customer
        event[PARAM_USER_SUB] = user_sub

        event_customer = event.get(CUSTOMER_ATTR)
        if user_customer != 'admin' and event_customer \
                and event_customer != user_customer:
            _LOG.warning(f'User \'{user_id}\' is not authorized to access '
                         f'\'{event_customer}\' customer.')
            return False

        roles = self.iam_service.role_batch_get(keys=role_names,
                                                customer=user_customer)
        roles = [r for r in roles
                 if not AccessControlService.is_role_expired(role=r)]
        if not roles:
            _LOG.debug(f'No valid roles found for user \'{user_id}\'')
            return False

        all_policy_names = list({p for r in roles for p in r.policies})
        policies = self.iam_service.policy_batch_get(keys=all_policy_names,
                                                     customer=user_customer)
        policy_structs = [PolicyStruct(p) for p in policies]

        for ps in policy_structs:
            if ps.forbids(target_permission):
                _LOG.debug(f'Policy \'{ps.name}\' explicitly forbids '
                           f'\'{target_permission}\'')
                return False

        is_allowed = any(ps.allows(target_permission) for ps in policy_structs)
        if not is_allowed:
            _LOG.debug(f'No policy allows \'{target_permission}\' '
                       f'for user \'{user_id}\'')
            return False

        target_user = event.get(PARAM_TARGET_USER)
        if target_user and not AccessControlService.is_allowed_target_user(
                user_id=user_id, target_user=target_user,
                user_customer=user_customer):
            return False

        permission_group = target_permission.rsplit(':', 1)[0]
        if permission_group in TENANT_SCOPED_PERMISSION_GROUPS:
            ta = TenantAccess()
            for ps in policy_structs:
                ta.add(ps)
            payload = ta.resolve_payload(target_permission)

            user_tenants = self.user_service.get_user_tenants(user=user_id)
            if user_tenants and user_tenants != ['*']:
                _LOG.debug(f'Restricting tenant access to user-level '
                           f'tenants: {user_tenants}')
                payload = payload.restrict_to(set(user_tenants))

            if payload.is_denying_all():
                _LOG.debug(f'All tenant access is denied for '
                           f'\'{target_permission}\' after policy '
                           f'resolution')
                return False

            event[PARAM_USER_TENANT_ACCESS] = payload

        _LOG.debug(f'Permission for user \'{user_id}\' on action: '
                   f'{target_permission} is granted')
        return True

    def get_role(self, name: str, customer: str = None):
        return self.iam_service.role_get(role_name=name, customer=customer)

    def get_policy(self, name: str, customer: str = None):
        return self.iam_service.policy_get(policy_name=name, customer=customer)

    def policy_exists(self, name: str, customer: str = None) -> bool:
        return bool(self.get_policy(name=name, customer=customer))

    def role_exists(self, name: str, customer: str = None) -> bool:
        return bool(self.get_role(name=name, customer=customer))

    @staticmethod
    def get_role_dto(role: Role):
        return role.get_json()

    @staticmethod
    def get_policy_dto(policy: Policy):
        return policy.get_json()

    @staticmethod
    def delete_entity(entity: Union[Role, Policy]):
        return entity.delete()

    def create_policy(self, policy_data: dict):
        name = policy_data.get(PARAM_NAME)
        if self.policy_exists(name=name):
            _LOG.warning(f'Policy  with name \'{name}\' already exists')

        return Policy(**policy_data)

    def create_role(self, role_data: dict):
        name = role_data.get(PARAM_NAME)
        if self.role_exists(name=name):
            _LOG.warning(f'Role with name \'{name}\' already exists')

        return Role(**role_data)

    @staticmethod
    def save(access_conf_object: Union[Role, Policy]):
        access_conf_object.save()

    @staticmethod
    def is_role_expired(role: Role):
        role_expiration_datetime = role.expiration
        if isinstance(role_expiration_datetime, str):
            role_expiration_datetime = datetime.fromisoformat(
                role_expiration_datetime)
        now = datetime.now()
        return now >= role_expiration_datetime

    def get_non_existing_permissions(self, permissions: list):
        permissions_mapping = self.setting_service.get_iam_permissions()

        nonexistent = []
        for permission in permissions:
            args = permission.split(':')
            if len(args) != 3:
                # permission don't match SERVICE:PERMISSION_GROUP:ACTION format
                nonexistent.append(permission)
                continue

            service, permission_group, action = args
            group = f'{service}:{permission_group}'
            if action not in permissions_mapping.get(group, []):
                nonexistent.append(permission)
        return nonexistent

    def get_non_existing_policies(self, policies: list):
        nonexistent = []
        for policy in policies:
            if not self.policy_exists(name=policy):
                nonexistent.append(policy)
        return nonexistent

    def get_non_existing_roles(self, roles: list):
        return [r for r in roles if not self.role_exists(name=r)]

    @staticmethod
    def is_allowed_target_user(user_id, target_user, user_customer):
        return user_customer == 'admin' or user_id == target_user

    def get_admin_permissions(self):
        permission_groups_mapping = self.setting_service.get_iam_permissions()
        if not permission_groups_mapping:
            return []
        permissions_list = []
        for group, available_actions in permission_groups_mapping.items():
            permissions_list.extend(
                [f'{group}:{action}' for action in available_actions])

        return permissions_list

    @staticmethod
    def get_role_default_expiration():
        current = datetime.now()
        expiration = current + timedelta(3 * 30)
        return expiration.isoformat()
