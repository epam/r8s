from tests.import_helper import add_src_to_path
from tests.test_handlers.test_algorithm_handler import TestAlgorithmHandler

add_src_to_path()


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

    def test_no_models_found(self):
        event = {'name': 'non-existing-model'}

        self.assert_exception_with_content(
            event=event, content=f'No algorithms found matching given query')


class TestsAlgorithmCreate(TestAlgorithmHandler):
    TESTED_METHOD_NAME = 'post'

    def test_empty_event(self):
        event = {}

        self.assert_exception_with_content(
            event=event, content=f'Bad Request. The following parameters '
                                 f'are missing:')

    def test_success(self):
        event = {
            'name': 'test_model3',
            'algorithm': 'xgboost',
            'customer': "test",
            "cloud": "AWS",
            'user_customer': 'admin',
            'required_data_attributes': ['cpu', 'memory', 'timestamp'],
            'metric_attributes': ['cpu', 'memory'],
            'timestamp_attribute': 'timestamp',
            'action': 'resize'
        }
        response = self.TESTED_METHOD(event=event)
        response_items = response.get('body').get('items')
        self.assert_status(response)

        self.assertEqual(len(response_items), 1)

        model = self.HANDLER.algorithm_service.get_by_name('test_model3')
        self.assertIsNotNone(model)

    def test_model_with_name_already_exist(self):
        event = {
            'name': 'test_model',
            'tenant': 'test_tenant',
            'body': {},
            'algorithm': 'xgboost',
            'customer': 'test_customer',
            'user_customer': 'admin',
            'required_data_attributes': ['cpu', 'memory', 'timestamp'],
            'metric_attributes': ['cpu', 'memory'],
            'timestamp_attribute': 'timestamp',
            'action': 'resize'
        }
        model_name = event.get('name')
        self.assert_exception_with_content(
            event=event, content=f'Model with name \'{model_name}\' '
                                 f'already exists')


class TestsAlgorithmUpdate(TestAlgorithmHandler):
    TESTED_METHOD_NAME = 'patch'

    def test_empty_event(self):
        event = {}

        self.assert_exception_with_content(
            event=event, content=f'Bad Request. The following parameters '
                                 f'are missing:')

    def test_success(self):
        clustering_settings = {
            'max_clusters': 10,
            'wcss_kmeans_max_iter': 100
        }
        recommendation_settings = {
            'record_step_minutes': 10,
            'max_days': 60,
            'min_allowed_days_schedule': 21
        }
        event = {
            'name': 'test_algorithm',
            'user_customer': 'admin',
            "clustering_settings": clustering_settings,
            'recommendation_settings': recommendation_settings
        }

        response = self.TESTED_METHOD(event=event)
        response_items = response.get('body').get('items')
        self.assert_status(response)

        self.assertEqual(len(response_items), 1)

        response_alg = response_items[0]

        self.assertEqual(response_alg.get('name'), event.get('name'))

        for key, value in clustering_settings.items():
            self.assertEqual(value, response_alg.get(
                'clustering_settings', {}).get(key))

        for key, value in recommendation_settings.items():
            self.assertEqual(value, response_alg.get(
                'recommendation_settings', {}).get(key))

    def test_update_nonexisting(self):
        event = {
            'name': 'test_algorithm',
            'user_customer': 'admin',
            "clustering_settings": {
                'max_clusters': 8,
                'wcss_kmeans_max_iter': 80
            },
        }
        algorithm_name = event.get('name')
        self.assert_exception_with_content(
            event=event,
            content=f'Algorithm with name \'{algorithm_name}\' '
                    f'does not exist.')


class TestsAlgorithmDelete(TestAlgorithmHandler):
    TESTED_METHOD_NAME = 'delete'

    def test_empty_event(self):
        event = {}

        self.assert_exception_with_content(
            event=event, content=f"Either 'id' or 'name' must be specified")

    def test_delete_nonexisting_name(self):
        event = {
            'name': 'non-existing-algorithm',
            'user_customer': 'admin',
        }

        self.assert_exception_with_content(
            event=event, content=f'No algorithm found matching given query')

    def test_delete_nonexisting_id(self):
        event = {
            'id': 'non-existing-algorithm-id',
            'user_customer': 'admin',
        }

        self.assert_exception_with_content(
            event=event, content=f'No algorithm found matching given query')

    def test_delete_success_name(self):
        event = {
            'name': self.algorithm1.name,
            'user_customer': 'admin',
        }

        response = self.TESTED_METHOD(event=event)
        self.assert_status(response)

        response_message = response.get('body').get('message')
        self.assertEqual(response_message,
                         f'Algorithm  with name \'{event.get("name")}\' '
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
