from commons.constants import DELETE_METHOD, USER_ID_ATTR, PATCH_METHOD, \
    PASSWORD_ATTR
from r8s.r8s_service.constants import PARAM_TARGET_USER
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from tests.test_handlers.test_user import TestUserHandler

NOT_ALLOWED_MESSAGE_PATH = 'not allowed'


class TestsUserDescribe(TestUserHandler):

    def test_list_users(self):
        event = {}
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)

        response_items = response.get('body').get('items')
        self.assertEqual(len(response_items), 3)

        response_usernames = [item.get('username') for item in response_items]
        self.assertEqual(set(response_usernames), {'user1', 'user2', 'user3'})

    def test_get_user(self):
        event = {
            'user_customer': 'admin',
            'target_user': 'user1'
        }
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)

        response_items = response.get('body').get('items')
        self.assertEqual(len(response_items), 1)

        self.assertEqual(response_items[0]['username'], 'user1')


class TestsUserPatch(TestUserHandler):
    @property
    def test_method(self):
        return PATCH_METHOD

    def test_patch_success(self):
        password = '12345asdAs$'
        event = {
            USER_ID_ATTR: 'user1',
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_TARGET_USER: 'user2',
            PASSWORD_ATTR: password
        }
        response = self.TESTED_METHOD(event=event)
        self.assert_status(response=response)

        self.cognito_client.set_password.assert_called_with(
            username='user2',
            password=password
        )

    def test_patch_invalid_password(self):
        password = 'too_short'
        event = {
            USER_ID_ATTR: 'user1',
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_TARGET_USER: 'user2',
            PASSWORD_ATTR: password
        }
        self.assert_exception_with_content(
            event=event, content='Password must have')

        self.cognito_client.set_password.assert_not_called()

    def test_patch_forbidden(self):
        password = 'too_short'
        event = {
            USER_ID_ATTR: 'user2',
            PARAM_USER_CUSTOMER: 'other',
            PARAM_TARGET_USER: 'user1',
            PASSWORD_ATTR: password
        }
        self.assert_exception_with_content(
            event=event, content=NOT_ALLOWED_MESSAGE_PATH)

        self.cognito_client.set_password.assert_not_called()


class TestsUserDelete(TestUserHandler):
    @property
    def test_method(self):
        return DELETE_METHOD

    def test_delete_success(self):
        event = {
            USER_ID_ATTR: 'user1',
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_TARGET_USER: 'user2'
        }
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)
        self.cognito_client.delete_user.assert_called_with(username='user2')

        message = response.get('body').get('message')
        self.assertIn("'user2' has been deleted", message)

    def test_forbidden_delete_other_customer(self):
        event = {
            USER_ID_ATTR: 'user2',
            PARAM_USER_CUSTOMER: 'other',
            PARAM_TARGET_USER: 'user3'
        }

        self.assert_exception_with_content(
            event=event, content=NOT_ALLOWED_MESSAGE_PATH)
        self.cognito_client.delete_user.assert_not_called()

    def test_forbidden_delete_admin(self):
        event = {
            USER_ID_ATTR: 'user2',
            PARAM_USER_CUSTOMER: 'other',
            PARAM_TARGET_USER: 'user1'
        }

        self.assert_exception_with_content(
            event=event, content=NOT_ALLOWED_MESSAGE_PATH)
        self.cognito_client.delete_user.assert_not_called()
