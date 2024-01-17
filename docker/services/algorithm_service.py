from datetime import datetime
from typing import Type

from bson import ObjectId
from bson.errors import InvalidId
from mongoengine import DoesNotExist, ValidationError, EmbeddedDocument

from commons.constants import CLUSTERING_SETTINGS_ATTR, METRIC_FORMAT_ATTR, \
    RECOMMENDATION_SETTINGS_ATTR, RESOURCE_TYPE_VM, ALGORITHM_MAPPING_ATTR
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
            _LOG.debug(f'Trying to convert to bson id')
            ObjectId(identifier)
            _LOG.debug(f'Describing algorithm by id')
            return self.get_by_id(object_id=identifier)
        except InvalidId:
            _LOG.debug(f'Describing algorithm by name')
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

    def update_from_licensed_job(self, algorithm: Algorithm,
                                 licensed_job: dict):
        licensed_algorithm_data = licensed_job.get(ALGORITHM_MAPPING_ATTR)[
            RESOURCE_TYPE_VM]
        cur_clust_settings = dict(algorithm.clustering_settings.to_mongo())
        cur_rec_settings = dict(algorithm.recommendation_settings.to_mongo())

        clustering_settings = licensed_algorithm_data.get(
            CLUSTERING_SETTINGS_ATTR)
        recommendation_settings = licensed_algorithm_data.get(
            RECOMMENDATION_SETTINGS_ATTR)

        if cur_clust_settings != clustering_settings:
            _LOG.warning(f'Updating algorithm \'{algorithm.name}\' '
                         f'clustering settings.')
            self.update_clustering_settings(
                algorithm=algorithm,
                clustering_settings=clustering_settings
            )
        if cur_rec_settings != recommendation_settings:
            _LOG.warning(f'Updating algorithm \'{algorithm.name}\' '
                         f'recommendation settings.')
            self.update_recommendation_settings(
                algorithm=algorithm,
                recommendation_settings=recommendation_settings
            )

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
