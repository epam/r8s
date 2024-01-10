from datetime import datetime
from typing import Type

from bson import ObjectId
from bson.errors import InvalidId
from mongoengine import DoesNotExist, ValidationError, EmbeddedDocument

from commons.constants import CLUSTERING_SETTINGS_ATTR, METRIC_FORMAT_ATTR, \
    RECOMMENDATION_SETTINGS_ATTR, ID_ATTR, ALGORITHM_ATTR, NAME_ATTR, \
    CUSTOMER_ATTR, LICENSED_ATTR, CLOUD_ATTR, REQUIRED_DATA_ATTRS_ATTR, \
    METRIC_ATTRS_ATTR, TIMESTAMP_ATTR, DEFAULT_METRIC_ATTRIBUTES, \
    DEFAULT_DATA_ATTRIBUTES
from commons.log_helper import get_logger
from models.algorithm import Algorithm, RecommendationSettings, \
    ClusteringSettings, MetricFormatSettings

_LOG = get_logger('r8s-algorithm-service')


class AlgorithmService:

    @staticmethod
    def list():
        return list(Algorithm.objects.all())

    def get(self, identifier: str):
        _LOG.debug(f'Describing algorithm by identifier: \'{identifier}\'')
        try:
            _LOG.debug('Trying to convert to bson id')
            ObjectId(identifier)
            _LOG.debug('Describing algorithm by id')
            return self.get_by_id(object_id=identifier)
        except InvalidId:
            _LOG.debug('Describing algorithm by name')
            return self.get_by_name(name=identifier)

    @staticmethod
    def get_by_id(object_id):
        try:
            return Algorithm.objects.get(id=object_id)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def get_by_name(name: str):
        try:
            return Algorithm.objects.get(name=name)
        except (DoesNotExist, ValidationError):
            return None

    @staticmethod
    def create(algorithm_data: dict):
        return Algorithm(**algorithm_data)

    @staticmethod
    def save(algorithm: Algorithm):
        algorithm.last_modified = datetime.utcnow()
        algorithm.md5 = algorithm.get_checksum()
        algorithm.save()

    @staticmethod
    def delete(algorithm: Algorithm):
        algorithm.delete()

    def sync_licensed_algorithm(self, license_data: dict, customer: str):
        algorithm_sync_data = license_data.get(ALGORITHM_ATTR)

        name = algorithm_sync_data.get(ID_ATTR)

        algorithm_obj: Algorithm = self.get_by_name(
            name=name)

        if not algorithm_obj:
            _LOG.debug('Creating new licensed algorithm')
            parameters = {
                NAME_ATTR: name,
                LICENSED_ATTR: True,
                CUSTOMER_ATTR: customer,
                CLOUD_ATTR: algorithm_sync_data.get(CLOUD_ATTR),
                REQUIRED_DATA_ATTRS_ATTR: DEFAULT_DATA_ATTRIBUTES,
                METRIC_ATTRS_ATTR: DEFAULT_METRIC_ATTRIBUTES,
                TIMESTAMP_ATTR: 'timestamp',
                CLUSTERING_SETTINGS_ATTR: algorithm_sync_data.get(
                    CLUSTERING_SETTINGS_ATTR),
                RECOMMENDATION_SETTINGS_ATTR: algorithm_sync_data.get(
                    RECOMMENDATION_SETTINGS_ATTR)
            }
            algorithm_obj = self.create(parameters)
            self.save(algorithm=algorithm_obj)
            return algorithm_obj
        _LOG.debug('Updating existing licensed algorithm')
        self.update_recommendation_settings(
            algorithm=algorithm_obj,
            recommendation_settings=algorithm_sync_data.get(
                RECOMMENDATION_SETTINGS_ATTR)
        )
        self.update_clustering_settings(
            algorithm=algorithm_obj,
            clustering_settings=algorithm_sync_data.get(
                CLUSTERING_SETTINGS_ATTR)
        )
        self.save(algorithm=algorithm_obj)
        return algorithm_obj

    def update_clustering_settings(self, algorithm: Algorithm,
                                   clustering_settings: dict):
        return self._update_embedded_document(
            algorithm=algorithm,
            attr_name=CLUSTERING_SETTINGS_ATTR,
            value=clustering_settings,
            document_class=ClusteringSettings
        )

    def update_metric_format_settings(self, algorithm: Algorithm,
                                      metric_format_settings: dict):
        return self._update_embedded_document(
            algorithm=algorithm,
            attr_name=METRIC_FORMAT_ATTR,
            value=metric_format_settings,
            document_class=MetricFormatSettings
        )

    def update_recommendation_settings(self, algorithm: Algorithm,
                                       recommendation_settings: dict):
        return self._update_embedded_document(
            algorithm=algorithm,
            attr_name=RECOMMENDATION_SETTINGS_ATTR,
            value=recommendation_settings,
            document_class=RecommendationSettings
        )

    @staticmethod
    def _update_embedded_document(algorithm: Algorithm,
                                  document_class: Type[EmbeddedDocument],
                                  attr_name: str, value: dict):
        try:
            document = algorithm.__getattribute__(attr_name)
        except AttributeError:
            _LOG.error(f'Attribute \'{attr_name}\' does not exist '
                       f'in algorithm model.')
            return
        if document:
            document_dict = dict(document.to_mongo())
        else:
            document_dict = {}
        document_dict.update(value)
        document = document_class(**document_dict)
        algorithm.__setattr__(attr_name, document)
        return algorithm
