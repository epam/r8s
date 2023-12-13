from unittest.mock import MagicMock

from commons.constants import (APPLICATION_ID_ATTR, DELETE_METHOD,
                               FORCE_ATTR, POST_METHOD, CUSTOMER_ATTR,
                               DESCRIPTION_ATTR, CLOUD_ATTR,
                               TENANT_LICENSE_KEY_ATTR, LICENSE_KEY_ATTR,
                               CUSTOMERS_ATTR, ALGORITHM_ID_ATTR)
from models.algorithm import Algorithm
from models.base_model import CloudEnum
from services.abstract_api_handler_lambda import PARAM_USER_CUSTOMER
from tests.test_handlers.test_licenses_application import \
    TestLicensesApplicationHandler
from modular_sdk.models.customer import Customer


class TestsLicensesApplicationDescribe(TestLicensesApplicationHandler):

    def test_list_success(self):
        event = {}
        response = self.TESTED_METHOD(event=event)

        self.assertEqual(len(response['body']['items']), 2)

        response_app_ids = {item.get('application_id')
                            for item in response['body']['items']}
        expected_app_ids = {self.license_application1.application_id,
                            self.license_application2.application_id}
        self.assertEqual(response_app_ids, expected_app_ids)

    def test_get_success(self):
        event = {
            APPLICATION_ID_ATTR: self.license_application1.application_id
        }
        self.application_service.resolve_application.return_value = [
            self.license_application1
        ]
        response = self.TESTED_METHOD(event=event)

        self.assertEqual(len(response['body']['items']), 1)
        self.assertEqual(response['body']['items'][0]['application_id'],
                         self.license_application1.application_id)

    def test_not_found(self):
        event = {}
        self.application_service.resolve_application.return_value = []

        self.assert_exception_with_content(
            event=event,
            content='No application found matching given query.'
        )


class TestsLicensesApplicationCreate(TestLicensesApplicationHandler):
    @property
    def test_method(self):
        return POST_METHOD

    def test_success(self):
        event = {
            CUSTOMER_ATTR: 'test',
            DESCRIPTION_ATTR: 'test',
            CLOUD_ATTR: 'AWS',
            TENANT_LICENSE_KEY_ATTR: 'key',
            PARAM_USER_CUSTOMER: 'test'
        }
        self.customer_service.get.return_value = Customer(name='test')

        license_response = MagicMock()
        license_response.status_code = 200
        license_response.json = MagicMock(return_value={
            'status_code': 200,
            'items': [{
                LICENSE_KEY_ATTR: 'license_key',
                CUSTOMERS_ATTR: {'test': []},
                ALGORITHM_ID_ATTR: 'algorithm',
                'allowance': {
                    'time_range': 'DAY',
                    'job_balance': 10,
                    'balance_exhaustion_model': 'independent'
                }
            }]})
        self.license_manager_client.activate_customer.return_value = (
            license_response)
        self.license_manager_client.retrieve_json.return_value = (
            license_response.json())

        self.license_manager_client.license_sync.return_value = (
            license_response)
        self.algorithm_service.sync_licensed_algorithm = MagicMock()

        self.algorithm_service.get_by_name = MagicMock(
            return_value=Algorithm(customer='test',
                                   name='algorithm',
                                   cloud=CloudEnum.CLOUD_AWS)

        )

        response = self.TESTED_METHOD(event=event)

        self.assertEqual(len(response['body']['items']), 1)
        response_license = response['body']['items'][0]
        meta = response_license.get('meta', {})
        self.assertEqual(meta['license_key'], 'license_key')
        self.assertEqual(meta['cloud'], 'AWS')
        self.assertEqual(meta['tenants'], ['*'])
        self.assertEqual(meta['algorithm'], 'algorithm')


class TestsLicensesApplicationDelete(TestLicensesApplicationHandler):
    @property
    def test_method(self):
        return DELETE_METHOD

    def test_delete_success(self):
        self.application_service.resolve_application.return_value = [
            self.license_application1
        ]
        event = {
            APPLICATION_ID_ATTR: self.license_application1.application_id
        }

        response = self.TESTED_METHOD(event=event)
        expected_message = (
            f'Application \'{self.license_application1.application_id}\' '
            f'has been deleted.'
        )
        self.assertIn(expected_message, response['body']['message'])
        self.application_service.mark_deleted.assert_called()
        self.application_service.force_delete.assert_not_called()

    def test_delete_force_success(self):
        self.application_service.resolve_application.return_value = [
            self.license_application1
        ]
        event = {
            APPLICATION_ID_ATTR: self.license_application1.application_id,
            FORCE_ATTR: True
        }

        response = self.TESTED_METHOD(event=event)
        expected_message = (
            f'Application \'{self.license_application1.application_id}\' '
            f'has been deleted.'
        )
        self.assertIn(expected_message, response['body']['message'])
        self.application_service.mark_deleted.assert_not_called()
        self.application_service.force_delete.assert_called()

    def test_not_found(self):
        self.application_service.resolve_application.return_value = []
        event = {
            APPLICATION_ID_ATTR: self.license_application1.application_id,
            FORCE_ATTR: True
        }

        expected_message = (
            f'Application {self.license_application1.application_id} '
            f'not found.'
        )
        self.assert_exception_with_content(
            event=event,
            content=expected_message
        )
        self.application_service.mark_deleted.assert_not_called()
        self.application_service.force_delete.assert_not_called()
