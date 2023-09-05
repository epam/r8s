import datetime
import json
import os
import shutil
from abc import ABC
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

import matplotlib.pyplot as plt
import pandas as pd

os.environ['r8s_mongodb_connection_uri'] = "mongomock://localhost/testdb"

from commons.constants import STATUS_OK, OK_MESSAGE


class BaseExecutorTest(TestCase, ABC):
    @patch.dict(os.environ,
                {'AWS_REGION': 'eu-central-1',
                 'r8s_mongodb_connection_uri': "mongomock://localhost/testdb"})
    def setUp(self) -> None:
        self.df = None
        self.instance_id = None
        self._init_algorithm()
        self._init_dirs()
        self._init_services()

    def tearDown(self) -> None:
        shutil.rmtree(self.reports_path)
        shutil.rmtree(self.metrics_dir_root)

    def _init_algorithm(self):
        from models.algorithm import Algorithm
        from models.base_model import CloudEnum

        data_attributes = ['instance_id', 'instance_type', 'timestamp',
                           'cpu_load', 'memory_load', 'net_output_load',
                           'avg_disk_iops', 'max_disk_iops']
        metric_attributes = ['cpu_load', 'memory_load', 'net_output_load',
                             'avg_disk_iops', 'max_disk_iops']
        algorithm = Algorithm(name='test_algorithm', customer="test",
                              cloud=CloudEnum.CLOUD_AWS,
                              required_data_attributes=data_attributes,
                              metric_attributes=metric_attributes,
                              timestamp_attribute='timestamp',
                              format_version='1.0')
        algorithm.recommendation_settings.target_timezone_name = None
        self.algorithm = algorithm

    def _init_dirs(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        reports_path = os.path.join(dir_path, 'test_reports')
        if not os.path.exists(reports_path):
            os.makedirs(reports_path)
        self.reports_path = reports_path

        metrics_dir_root = os.path.join(dir_path, 'test_metrics')
        self.metrics_dir_root = metrics_dir_root

        metrics_dir = os.path.join(metrics_dir_root, 'customer', 'aws',
                                   'TEST_TENANT', 'eu-central-1', 'timestamp')
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)
        self.metrics_dir = metrics_dir

        plots_dir = os.path.join(metrics_dir, 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir)
        self.plots_dir = plots_dir

    def _init_services(self):
        from services.environment_service import EnvironmentService
        self.environment_service = EnvironmentService()

        from services.clustering_service import ClusteringService
        self.clustering_service = ClusteringService()

        from services.metrics_service import MetricsService
        self.metrics_service = MetricsService(
            clustering_service=self.clustering_service)

        from services.schedule.schedule_service import ScheduleService
        self.schedule_service = ScheduleService(
            metrics_service=self.metrics_service
        )

        from services.shape_service import ShapeService
        self.shape_service = ShapeService()

        from services.shape_price_service import ShapePriceService
        self.shape_price_service = ShapePriceService()

        aws_isntances_data_path = self._get_aws_instance_data_path()
        with open(aws_isntances_data_path, 'r') as f:
            aws_instances_data = json.load(f)

        aws_instances_pricing_path = self._get_aws_instance_pricing_path()
        with open(aws_instances_pricing_path, 'r') as f:
            aws_instance_prices = json.load(f)

        self.populate_shapes(
            aws_instances_data=aws_instances_data,
            aws_instance_prices=aws_instance_prices
        )

        settings_service = MagicMock()
        settings_service.get_aws_instances_data = MagicMock(
            return_value=aws_instances_data)

        settings_service.get_aws_instance_prices = MagicMock(
            return_value=aws_instance_prices
        )

        from services.customer_preferences_service import \
            CustomerPreferencesService
        customer_prefs_service = CustomerPreferencesService()

        from services.resize.resize_service import ResizeService
        self.resize_service = ResizeService(
            shape_service=self.shape_service,
            shape_price_service=self.shape_price_service,
            customer_preferences_service=customer_prefs_service)

        from services.saving.saving_service import SavingService
        self.saving_service = SavingService(
            shape_price_service=self.shape_price_service
        )

        from services.meta_service import MetaService
        self.meta_service = MetaService(
            environment_service=self.environment_service)

        from services.recommendation_history_service import \
            RecommendationHistoryService
        self.recommendation_history_service = RecommendationHistoryService()

        from services.recomendation_service import RecommendationService
        self.recommendation_service = RecommendationService(
            metrics_service=self.metrics_service,
            schedule_service=self.schedule_service,
            resize_service=self.resize_service,
            environment_service=self.environment_service,
            saving_service=self.saving_service,
            meta_service=self.meta_service,
            recommendation_history_service=self.recommendation_history_service
        )

    def assert_stats(self, result, status=STATUS_OK,
                     message_contains=OK_MESSAGE):
        stats = result.get('stats', {})
        status_ = stats.get('status')
        message_ = stats.get('message')

        self.assertEqual(status_, status)
        self.assertTrue(message_contains in message_)

    def assert_action(self, result, expected_actions):
        self.assertEqual(set(expected_actions),
                         set(result['general_actions']))

    def create_plots(self):
        if self.df is None:
            return

        freq_mapping = {
            7: '20Min',
            14: '40Min',
            30: '60Min'
        }
        plot_df = self.df.drop(
            self.df.columns.difference(['cpu_load', 'memory_load']), 1,
            inplace=False)
        for days, freq in freq_mapping.items():
            df = plot_df.groupby(pd.Grouper(freq=freq)).mean()
            df = self._get_last_period(df, days=days)

            plt.figure()
            df.plot()
            plt.legend(loc='best')
            instance_plot_dir = os.path.join(self.plots_dir, self.instance_id)
            if not os.path.exists(instance_plot_dir):
                os.makedirs(instance_plot_dir)
            file_path = os.path.join(instance_plot_dir,
                                     f'{days}_days_plot.png')
            plt.savefig(file_path)
            plt.close('all')

    @staticmethod
    def _get_last_period(df, days=7):
        range_max = df.index.max()
        range_min = range_max - datetime.timedelta(days=days)

        # take slice with final week of data
        sliced_df = df[(df.index >= range_min) &
                       (df.index <= range_max)]
        return sliced_df

    @staticmethod
    def populate_shapes(aws_instances_data, aws_instance_prices):
        from models.shape_price import ShapePrice
        from models.shape import Shape
        price_mapping = {k['name']: k for k in aws_instance_prices}
        shape_mapping = {k['name']: k for k in aws_instances_data}

        for shape_name, shape_data in shape_mapping.items():
            shape_pricing = price_mapping.get(shape_name)
            if not shape_pricing:
                continue
            price_item = {
                'cloud': shape_pricing.get('cloud'),
                'name': shape_pricing.get('name'),
                'region': shape_pricing.get('region'),
                'os': shape_pricing.get('os').upper(),
                'on_demand': shape_pricing.get('price').get('on_demand'),
            }
            shape_price_item = ShapePrice(**price_item)
            shape_price_item.save()

            shape_obj_data = {
                'name': shape_name,
                'cloud': shape_data.get('cloud'),
                'cpu': shape_data.get('cpu'),
                'memory': shape_data.get('memory'),
                'network_throughput': shape_data.get('network_throughput'),
                'iops': shape_data.get('iops'),
                'family_type': shape_data.get('family_type'),
                'physical_processor': shape_data.get('physical_processor'),
                'architecture': shape_data.get('architecture'),
            }
            shape_obj = Shape(**shape_obj_data)
            shape_obj.save()

    def _get_aws_instance_data_path(self):
        root = self.__get_root_dir()
        return os.path.join(root, "scripts", 'aws_instances_data.json')

    def _get_aws_instance_pricing_path(self):
        root = self.__get_root_dir()
        return os.path.join(root, "scripts", 'aws_instance_prices.json')

    @staticmethod
    def __get_root_dir():
        return Path(os.path.dirname(os.path.realpath(__file__))).parent.parent
