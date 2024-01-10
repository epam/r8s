from commons.constants import POST_METHOD, DELETE_METHOD
from tests.test_handlers.test_algorithm import TestAlgorithmHandler

ERROR_NO_ALGORITHMS = 'No algorithm found matching given query'


class TestsAlgorithmDescribe(TestAlgorithmHandler):
    TESTED_METHOD_NAME = 'get'

    def test_algorithm_list(self):
        event = {'user_customer': 'admin'}
        response = self.TESTED_METHOD(event=event)

        self.assert_status(response=response)

        response_items = response['body']['items']
        self.assertEqual(len(response_items), 2)

        model_names = set([item.get('name') for item in response_items])
        self.assertEqual(model_names, {'test_algorithm', 'test_algorithm2'})

    def test_get_by_id(self):
        algorithm_dto = self.algorithm1.get_dto()
        model_id = str(self.algorithm1.get_json().get('_id'))
        event = {'id': model_id, 'user_customer': 'admin'}

        response = self.TESTED_METHOD(event=event)

        self.assert_status(response)

        response_items = response['body']['items']
        self.assertEqual(len(response_items), 1)
        self.assertEqual(algorithm_dto.get('name'),
                         response_items[0].get('name'))

    def test_get_by_name(self):
        algorithm_dto = self.algorithm1.get_dto()
        event = {'name': algorithm_dto.get('name'),
                 'user_customer': 'admin'}

        response = self.TESTED_METHOD(event=event)

        self.assert_status(response)

        response_items = response['body']['items']
        self.assertEqual(len(response_items), 1)
        self.assertEqual(algorithm_dto.get('name'),
                         response_items[0].get('name'))

    def test_no_algorithms_found(self):
        event = {'name': 'non-existing-algorithm'}

        self.assert_exception_with_content(
            event=event, content=ERROR_NO_ALGORITHMS)


class TestsAlgorithmCreate(TestAlgorithmHandler):
    @property
    def test_method(self):
        return POST_METHOD

    def test_empty_event(self):
        event = {}

        self.assert_exception_with_content(
            event=event, content='Bad Request. The following parameters '
                                 'are missing:')


class TestsAlgorithmDelete(TestAlgorithmHandler):
    @property
    def test_method(self):
        return DELETE_METHOD

    def test_empty_event(self):
        event = {}

        self.assert_exception_with_content(
            event=event, content="Either 'id' or 'name' must be specified")

    def test_delete_non_existing_name(self):
        event = {
            'name': 'non-existing-algorithm',
            'user_customer': 'admin',
        }

        self.assert_exception_with_content(
            event=event, content=ERROR_NO_ALGORITHMS)

    def test_delete_non_existing_id(self):
        event = {
            'id': 'non-existing-algorithm-id',
            'user_customer': 'admin',
        }

        self.assert_exception_with_content(
            event=event, content=ERROR_NO_ALGORITHMS)

    def test_delete_success_name(self):
        event = {
            'name': self.algorithm1.name,
            'user_customer': 'admin',
        }

        response = self.TESTED_METHOD(event=event)
        self.assert_status(response)

        response_message = response.get('body').get('message')
        self.assertEqual(response_message,
                         f'Algorithm with name \'{event.get("name")}\' '
                         f'has been deleted')

    def test_delete_success_id(self):
        algorithm_id = str(self.algorithm1.id)
        event = {
            'id': algorithm_id,
            'user_customer': 'admin',
        }

        response = self.TESTED_METHOD(event=event)
        self.assert_status(response)

        response_message = response.get('body').get('message')
        self.assertEqual(response_message,
                         f'Algorithm with id \'{event.get("id")}\' '
                         f'has been deleted')
