from unittest.mock import MagicMock

from tests.test_handlers.test_storage_handler import TestStorageHandler
from tests.import_helper import add_src_to_path

add_src_to_path()


class TestsStorageDescribe(TestStorageHandler):
    TESTED_METHOD_NAME = 'get'

    def test_list_storages(self):
        event = {}
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)

        response_items = response.get('body').get('items')
        self.assertEqual(len(response_items), 2)

        response_storage_names = [item.get('name') for item in response_items]
        self.assertEqual(set(response_storage_names), {self.storage1.name,
                                                       self.storage2.name})

    def test_list_storages_empty(self):
        self.HANDLER.storage_service = MagicMock()
        self.HANDLER.storage_service.list.return_value = []
        event = {}

        self.assert_exception_with_content(
            event, 'No storages matching given query')

    def test_get_storage_by_name(self):
        event = {
            'name': self.storage1.name
        }
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)
        response_items = response.get('body').get('items')
        self.assertEqual(len(response_items), 1)

        self.assertEqual(response_items[0].get('name'), event.get('name'))

    def test_get_nonexisting_storage_by_name(self):
        event = {
            'name': 'nonexistingstorage'
        }

        self.assert_exception_with_content(
            event, 'No storages matching given query')

    def test_get_nonexisting_storage_by_id(self):
        event = {
            'id': 'nonexistingstorage'
        }

        self.assert_exception_with_content(
            event, 'No storages matching given query')

    def test_get_storage_by_id(self):
        event = {
            'id': self.storage1.get_dto().get('_id')
        }
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)
        response_items = response.get('body').get('items')
        self.assertEqual(len(response_items), 1)

        self.assertEqual(response_items[0].get('_id'), event.get('id'))


class TestsStorageCreate(TestStorageHandler):
    TESTED_METHOD_NAME = 'post'

    def test_storage_post_empty_event(self):
        event = {}
        self.assert_exception_with_content(
            event,
            "The following parameters are missing: ['name', 'type', "
            "'access']")

    def test_storage_post_success(self):
        event = {
            'name': 'test_storage_3',
            'service': 'S3_BUCKET',
            'type': 'STORAGE',
            'access': {'bucket_name': 'test_bucket', 'prefix': 'test/'}
        }

        response = self.TESTED_METHOD(event=event)
        self.mocked_s3_client.is_bucket_exists.assert_called()
        self.assert_status(response)

        items = response.get('body').get('items')
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get('name'), event.get('name'))
        self.assertEqual(item.get('tenant'), event.get('tenant'))
        self.assertEqual(item.get('service'), event.get('service'))
        self.assertEqual(item.get('access'), event.get('access'))

    def test_storage_post_already_exist(self):
        event = {
            'name': self.storage1.name,
            'service': 'S3_BUCKET',
            'type': 'STORAGE',
            'access': {'bucket_name': 'test_bucket', 'prefix': 'test/'}
        }
        self.assert_exception_with_content(
            event,
            f"Storage with name '{self.storage1.name}' already exists.")


class TestsStorageUpdate(TestStorageHandler):
    TESTED_METHOD_NAME = 'patch'

    def test_storage_update_empty_event(self):
        event = {}
        self.assert_exception_with_content(
            event,
            "The following parameters are missing: ['name']")

    def test_storage_update_success(self):
        event = {
            'name': self.storage1.name,
            'service': 'S3_BUCKET',
            'type': 'DATA_SOURCE',
            'access': {'bucket_name': 'test_bucket', 'prefix': 'test/updated'}
        }
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response)
        items = response.get('body').get('items')
        self.assertEqual(len(items), 1)

        item = items[0]

        self.assertEqual(item.get('name'), event.get('name'))
        self.assertEqual(item.get('tenant'), event.get('tenant'))
        self.assertEqual(item.get('type'), event.get('type'))
        self.assertEqual(item.get('access'), event.get('access'))

    def test_storage_update_nonexisting(self):
        event = {
            'name': 'nonexisting-storage',
            'service': 'S3_BUCKET',
            'type': 'DATA_SOURCE',
            'access': {'bucket_name': 'test_bucket', 'prefix': 'test/updated'}
        }
        self.assert_exception_with_content(
            event,
            f'Storage with name \'{event.get("name")}\' does not exists.')


class TestsStorageDelete(TestStorageHandler):
    TESTED_METHOD_NAME = 'delete'

    def test_storage_delete_empty_event(self):
        event = {}
        self.assert_exception_with_content(
            event, "Either 'id' or 'name' must be specified")

    def test_storage_delete_success(self):
        event = {
            'name': self.storage1.name
        }
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response)
        message = response.get('body').get('message')
        self.assertEqual(message, f"Storage with name '{self.storage1.name}' "
                                  f"has been deleted")

    def test_storage_delete_not_exist(self):
        event = {
            'name': 'non-existing-storage'
        }

        self.assert_exception_with_content(
            event, "No storage found matching given query")
