from unittest.mock import MagicMock

from commons.constants import PARENT_ID_ATTR, DELETE_METHOD, FORCE_ATTR, \
    POST_METHOD, APPLICATION_ID_ATTR, DESCRIPTION_ATTR, SCOPE_ATTR
from r8s.r8s_service.constants import PARAM_PARENT_ID
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from tests.test_handlers.test_parent import TestParentHandler

NO_PARENTS_ERROR = 'No Parents found matching given query'
NO_APPLICATIONS_ERROR = 'No application found matching given query'


class TestsParentDescribe(TestParentHandler):

    def test_parent_list(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin'
        }
        self.parent_service.list_application_parents = MagicMock(
            return_value=[self.parent1, self.parent2])
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)
        self.assertEqual(len(response['body']['items']), 2)

    def test_parent_get(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARENT_ID_ATTR: 'parent1'
        }
        self.parent_service.list_application_parents = MagicMock(
            return_value=[self.parent1])
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)
        self.assertEqual(len(response['body']['items']), 1)

    def test_parent_get_non_existing(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARENT_ID_ATTR: 'parent3'
        }
        self.parent_service.list_application_parents = MagicMock(
            return_value=[])

        self.assert_exception_with_content(
            event, NO_PARENTS_ERROR)

    def test_parent_get_no_applications(self):
        self.application_service.resolve_application.return_value = []
        event = {
            PARAM_USER_CUSTOMER: 'admin'
        }

        self.assert_exception_with_content(
            event, NO_APPLICATIONS_ERROR)


class TestsParentCreate(TestParentHandler):
    @property
    def test_method(self):
        return POST_METHOD

    def test_success(self):
        event = {
            APPLICATION_ID_ATTR: 'license_application',
            DESCRIPTION_ATTR: 'description',
            SCOPE_ATTR: 'ALL'
        }
        self.application_service.get_application_meta = MagicMock(
            return_value=self.license_application.meta)
        self.customer_service.get.return_value = True
        self.parent_service.save = MagicMock(return_value=True)
        response = self.TESTED_METHOD(event=event)

        self.assertEqual(len(response['body']['items']), 1)
        self.parent_service.save.assert_called()

    def test_application_not_found(self):
        event = {
            APPLICATION_ID_ATTR: 'license_application',
            DESCRIPTION_ATTR: 'description',
            SCOPE_ATTR: 'ALL'
        }
        self.application_service.resolve_application.return_value = []

        self.assert_exception_with_content(
            event=event, content=NO_APPLICATIONS_ERROR)

        self.parent_service.save.assert_not_called()

    def test_multiple_applications_found(self):
        event = {
            APPLICATION_ID_ATTR: 'license_application',
            DESCRIPTION_ATTR: 'description',
            SCOPE_ATTR: 'ALL'
        }
        self.application_service.resolve_application.return_value = [
            1, 2
        ]

        self.assert_exception_with_content(
            event=event, content='Exactly one application must be identified')

        self.parent_service.save.assert_not_called()


class TestsParentDelete(TestParentHandler):
    @property
    def test_method(self):
        return DELETE_METHOD

    def test_delete_success(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_PARENT_ID: 'parent1'
        }
        self.parent_service.get_parent_by_id = MagicMock(
            return_value=self.parent1)

        response = self.TESTED_METHOD(event=event)
        self.assertIn("'parent1' has been deleted",
                      response['body']['message'])
        self.parent_service.mark_deleted.assert_called()

    def test_delete_success_force(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_PARENT_ID: 'parent1',
            FORCE_ATTR: True
        }
        self.parent_service.get_parent_by_id = MagicMock(
            return_value=self.parent1)

        response = self.TESTED_METHOD(event=event)
        self.assertIn("'parent1' has been deleted",
                      response['body']['message'])
        self.parent_service.force_delete.assert_called()

    def test_already_deleted(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_PARENT_ID: 'parent1'
        }
        self.parent1.is_deleted = True
        self.parent_service.get_parent_by_id = MagicMock(
            return_value=self.parent1)

        response = self.TESTED_METHOD(event=event)
        self.assertIn(
            'already marked as deleted',
            response['body']['message']
        )
        self.parent_service.mark_deleted.assert_not_called()
        self.parent_service.force_delete.assert_not_called()

    def test_parent_not_found(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_PARENT_ID: 'parent1'
        }
        self.parent_service.get_parent_by_id = MagicMock(return_value=None)

        self.assert_exception_with_content(
            event=event, content='Parent \'parent1\' does not exist.')
        self.parent_service.mark_deleted.assert_not_called()
        self.parent_service.force_delete.assert_not_called()

    def test_application_not_found(self):
        event = {
            PARAM_USER_CUSTOMER: 'admin',
            PARAM_PARENT_ID: 'parent1'
        }
        self.application_service.resolve_application.return_value = []

        self.assert_exception_with_content(
            event=event, content=NO_APPLICATIONS_ERROR)

        self.parent_service.mark_deleted.assert_not_called()
        self.parent_service.force_delete.assert_not_called()
