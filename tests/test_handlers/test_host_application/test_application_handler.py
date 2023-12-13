from unittest.mock import MagicMock
from modular_sdk.models.parent import Parent

from commons.constants import POST_METHOD, APPLICATION_ID_ATTR, DELETE_METHOD, \
    FORCE_ATTR, CUSTOMER_ATTR, DESCRIPTION_ATTR, INPUT_STORAGE_ATTR, \
    OUTPUT_STORAGE_ATTR, USERNAME_ATTR, PASSWORD_ATTR, CONNECTION_ATTR, \
    HOST_ATTR
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from tests.test_handlers.test_host_application import \
    TestHostApplicationHandler


class TestsHostApplicationDescribe(TestHostApplicationHandler):

    def test_list_success(self):
        event = {}
        response = self.TESTED_METHOD(event=event)

        self.assertEqual(len(response['body']['items']), 1)

    def test_not_found(self):
        event = {}
        self.application_service.resolve_application.return_value = None

        self.assert_exception_with_content(
            event=event,
            content='No application found matching given query.'
        )


class TestsHostApplicationCreate(TestHostApplicationHandler):
    @property
    def test_method(self):
        return POST_METHOD

    def test_create_success(self):
        event = {
            CUSTOMER_ATTR: "test",
            PARAM_USER_CUSTOMER: "admin",
            DESCRIPTION_ATTR: "test",
            INPUT_STORAGE_ATTR: "input",
            OUTPUT_STORAGE_ATTR: "output",
            CONNECTION_ATTR: {
                HOST_ATTR: 'host',
                USERNAME_ATTR: 'username',
                PASSWORD_ATTR: 'password'
            },
        }
        self.application_service._create_application_secret = MagicMock(
            return_value='secret_name')
        self.parent_service.save = MagicMock(
            return_value=Parent(parent_id='test')
        )
        response = self.TESTED_METHOD(event=event)

        response = response['body']['items'][0]
        self.assertEqual(response[DESCRIPTION_ATTR],
                         event[DESCRIPTION_ATTR])
        self.assertEqual(response['meta'][INPUT_STORAGE_ATTR],
                         event[INPUT_STORAGE_ATTR])
        self.assertEqual(response['meta'][OUTPUT_STORAGE_ATTR],
                         event[OUTPUT_STORAGE_ATTR])
        self.assertEqual(response['meta'][CONNECTION_ATTR][HOST_ATTR],
                         event[CONNECTION_ATTR][HOST_ATTR])


class TestsHostApplicationDelete(TestHostApplicationHandler):
    @property
    def test_method(self):
        return DELETE_METHOD

    def test_delete_success(self):
        event = {
            APPLICATION_ID_ATTR: self.host_application.application_id
        }

        self.parent_service.list_application_parents = MagicMock(
            return_value=[Parent(parent_id='1'), Parent(parent_id='1')]
        )
        self.parent_service.mark_deleted = MagicMock(
            return_value=True)

        response = self.TESTED_METHOD(event=event)
        expected_message = (
            f'Application \'{self.host_application.application_id}\' '
            f'has been deleted.'
        )
        self.assertIn(expected_message, response['body']['message'])
        self.application_service.mark_deleted.assert_called()

    def test_delete_force_success(self):
        event = {
            APPLICATION_ID_ATTR: self.host_application.application_id,
            FORCE_ATTR: True
        }

        self.parent_service.list_application_parents = MagicMock(
            return_value=[Parent(parent_id='1'), Parent(parent_id='1')]
        )
        self.parent_service.mark_deleted = MagicMock(
            return_value=True)

        response = self.TESTED_METHOD(event=event)
        expected_message = (
            f'Application \'{self.host_application.application_id}\' '
            f'has been deleted.'
        )
        self.assertIn(expected_message, response['body']['message'])
        self.application_service.mark_deleted.assert_not_called()
        self.application_service.force_delete.assert_called()

    def test_not_found(self):
        event = {
            APPLICATION_ID_ATTR: self.host_application.application_id
        }
        self.application_service.resolve_application.return_value = None

        expected_message = (
            f'Application with id '
            f'\'{self.host_application.application_id}\' does not exist.'
        )
        self.assert_exception_with_content(
            event=event,
            content=expected_message
        )
        self.application_service.mark_deleted.assert_not_called()
        self.application_service.force_delete.assert_not_called()
