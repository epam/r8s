from datetime import datetime, timedelta
from unittest.mock import MagicMock

from commons.constants import SETTING_IAM_PERMISSIONS
from models.policy import Policy
from models.role import Role
from models.setting import Setting
from services.rbac.access_control_service import AccessControlService
from services.rbac.iam_service import IamService
from services.setting_service import SettingsService
from services.user_service import CognitoUserService
from tests.test_handlers.abstract_test_processor_handler import \
    AbstractTestProcessorHandler


class TestUserHandler(AbstractTestProcessorHandler):
    processor_name = 'user_processor'

    def build_processor(self):
        self.cognito_client = MagicMock()

        self.user_service = CognitoUserService(self.cognito_client)
        self.iam_service = IamService()
        self.settings_service = SettingsService()
        self.access_control_service = AccessControlService(
            iam_service=self.iam_service,
            user_service=self.user_service,
            setting_service=self.settings_service
        )

        return self.handler_module.UserProcessor(
            user_service=self.user_service,
            access_control_service=self.access_control_service,
            iam_service=self.iam_service
        )

    def init_data(self):
        self.cognito_client.get_user.return_value = {'Username': "user1"}
        self.cognito_client.list_users.return_value = {
            'Users': [
                {'Username': "user1"},
                {'Username': "user2"},
                {'Username': "user3"},
            ]}
        self.cognito_client.delete_user.return_value = None
        self.cognito_client.get_user_customer.side_effect = (
            self._get_user_customer)
        self.cognito_client.set_password.return_value = None

        iam_permissions = Setting(
            name=SETTING_IAM_PERMISSIONS,
            value=[
                "r8s:iam:describe_policy",
                "r8s:iam:create_policy",
                "r8s:iam:update_policy",
                "r8s:iam:remove_policy",
                "r8s:iam:describe_role",
                "r8s:iam:create_role",
                "r8s:iam:update_role",
                "r8s:iam:remove_role",
            ]
        )
        iam_permissions.save()
        self.setting = iam_permissions
        policy = Policy(
            name='policy1',
            permissions=[
                "r8s:iam:describe_policy",
                "r8s:iam:create_policy",
                "r8s:iam:update_policy",
                "r8s:iam:remove_policy",
                "r8s:iam:describe_role",
                "r8s:iam:create_role",
                "r8s:iam:update_role",
                "r8s:iam:remove_role",
            ]
        )
        policy.save()
        self.policy = policy

        role = Role(
            name='role1',
            expiration=(datetime.now() + timedelta(days=30)).isoformat(),
            policies=[self.policy.name],
            resource=['*']
        )
        role.save()
        self.role = role

        self.objects = [self.setting, self.policy, self.role]

    def tearDown(self) -> None:
        for obj_ in self.objects:
            obj_.delete()

    @staticmethod
    def _get_user_customer(username):
        if username == 'user1':
            return 'admin'
        else:
            return f'other-{username}'
