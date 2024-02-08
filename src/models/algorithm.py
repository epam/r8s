import hashlib
import json
from datetime import datetime

from mongoengine import StringField, ListField, IntField, EnumField, \
    EmbeddedDocument, BooleanField, EmbeddedDocumentField, DateTimeField

from commons.enum import ListEnum
from models.base_model import BaseModel, CloudEnum


class QuotingEnum(ListEnum):
    QUOTE_MINIMAL = 0
    QUOTE_ALL = 1
    QUOTE_NONNUMERIC = 2
    QUOTE_NONE = 3


class ShapeSorting(ListEnum):
    SORT_BY_PRICE = 'PRICE'
    SORT_BY_PERFORMANCE = 'PERFORMANCE'


class ShapeCompatibilityRule(ListEnum):
    RULE_NONE = 'NONE'
    RULE_ONLY_SAME = 'SAME'
    RULE_ONLY_COMPATIBLE = 'COMPATIBLE'


class AnalysisPriceEnum(ListEnum):
    DEFAULT = 'DEFAULT'
    CUSTOMER_MIN = 'CUSTOMER_MIN'
    CUSTOMER_MAX = 'CUSTOMER_MAX'
    CUSTOMER_AVG = 'CUSTOMER_AVG'


class InterpMethodEnum(ListEnum):
    INTERP1D = 'interp1d'
    POLYMONIAL = 'polynomial'


class KMeansInitEnum(ListEnum):
    KMEANS = 'k-means++'
    RANDOM = 'random'


class MetricFormatSettings(EmbeddedDocument):
    delimiter = StringField(null=True, min_length=1, max_length=2)
    skipinitialspace = BooleanField(null=True)
    lineterminator = StringField(null=True, min_length=1, max_length=3)
    quotechar = StringField(null=True, min_length=1, max_length=1)
    quoting = EnumField(QuotingEnum, null=True)
    escapechar = StringField(null=True, min_length=1, max_length=1)
    doublequote = BooleanField(null=True)


class ClusteringSettings(EmbeddedDocument):
    max_clusters = IntField(min_value=1, max_value=10, default=5)
    wcss_kmeans_init = EnumField(KMeansInitEnum,
                                 default=KMeansInitEnum.KMEANS)
    wcss_kmeans_max_iter = IntField(min_value=1, default=300, max_value=1000)
    wcss_kmeans_n_init = IntField(min_value=1, default=10, max_value=100)
    knee_interp_method = EnumField(InterpMethodEnum,
                                   default=InterpMethodEnum.POLYMONIAL)
    knee_polynomial_degree = IntField(default=5, min_value=1, max_value=20)


class RecommendationSettings(EmbeddedDocument):
    record_step_minutes = IntField(min_value=1, max_value=60, default=5)
    thresholds = ListField(field=IntField(null=True, min_value=0,
                                          max_value=100),
                           max_length=3, default=[10, 30, 70])
    min_allowed_days = IntField(default=1, min_value=1, max_value=90)
    max_days = IntField(default=90, min_value=7, max_value=365)
    min_allowed_days_schedule = IntField(default=14, min_value=7, max_value=60)
    max_allowed_days_schedule = IntField(default=28, min_value=14)
    min_schedule_day_duration_minutes = IntField(default=90, min_value=30,
                                                 max_value=360)

    ignore_savings = BooleanField(default=False)
    max_recommended_shapes = IntField(min_value=1, max_value=10, default=5)
    shape_compatibility_rule = EnumField(
        ShapeCompatibilityRule,
        default=ShapeCompatibilityRule.RULE_NONE)
    shape_sorting = EnumField(ShapeSorting,
                              default=ShapeSorting.SORT_BY_PERFORMANCE)
    use_past_recommendations = BooleanField(default=True)
    use_instance_tags = BooleanField(default=True)
    analysis_price = EnumField(AnalysisPriceEnum,
                               default=AnalysisPriceEnum.DEFAULT)
    allowed_actions = ListField(StringField(null=True))
    ignore_actions = ListField(StringField(null=True))
    discard_initial_zeros = BooleanField(default=True)
    target_timezone_name = StringField(default="Europe/London")
    forbid_change_series = BooleanField(default=False)
    forbid_change_family = BooleanField(default=False)
    optimized_aggregation_threshold_days = IntField(default=14)
    optimized_aggregation_step_minutes = IntField(default=15)


class Algorithm(BaseModel):
    dto_skip_attrs = ['_id', 'md5', 'format_version']

    name = StringField(unique=True)
    resource_type = StringField(null=True)
    customer = StringField(null=True)
    cloud = EnumField(CloudEnum)
    licensed = BooleanField(default=False)
    metric_format = EmbeddedDocumentField(MetricFormatSettings, null=True)
    required_data_attributes = ListField(StringField(null=True))
    metric_attributes = ListField(StringField(null=True))
    timestamp_attribute = StringField(null=True)

    clustering_settings = EmbeddedDocumentField(ClusteringSettings,
                                                default=ClusteringSettings())
    recommendation_settings = EmbeddedDocumentField(
        RecommendationSettings,
        default=RecommendationSettings())

    last_modified = DateTimeField(null=False, default=datetime.utcnow)
    md5 = StringField(null=True)
    format_version = StringField(null=True)

    def get_dto(self):
        algorithm_dto = super(Algorithm, self).get_dto()
        last_modified = algorithm_dto.get('last_modified')
        if isinstance(last_modified, datetime):
            algorithm_dto['last_modified'] = last_modified.isoformat()
        return algorithm_dto

    def get_read_configuration(self):
        if not self.metric_format:
            return {}
        return {k: v for k, v in self.metric_format.to_mongo().items() if v}

    def checksum_matches(self):
        md5 = self.get_checksum()
        return md5 == self.md5

    def get_checksum(self):
        algorithm_data = self.get_json()
        algorithm_data.pop('md5', None)
        algorithm_data.pop('_id', None)

        if self.last_modified:
            algorithm_data['last_modified'] = self.last_modified.isoformat(
                timespec='seconds')

        data_str = json.dumps(algorithm_data, sort_keys=True).encode('utf-8')
        return hashlib.md5(data_str).hexdigest()
