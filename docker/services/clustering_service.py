import numpy
import pandas as pd
from kneed import KneeLocator
from sklearn.cluster import KMeans
from tslearn.clustering import TimeSeriesKMeans

from commons.constants import COLUMN_MEMORY_LOAD, COLUMN_CPU_LOAD
from models.algorithm import Algorithm


class ClusteringService:

    def cluster(self, df: pd.DataFrame,
                algorithm: Algorithm):
        df_ = self._preprocess(df=df,
                               column_names=algorithm.metric_attributes)
        n_clusters = self.get_optimal_clusters_number(
            df=df_,
            algorithm=algorithm
        )
        kmeans = TimeSeriesKMeans(n_clusters=n_clusters).fit(df_)
        centroids = kmeans.cluster_centers_
        df['cluster'] = kmeans.labels_

        centroids = self._convert_centroids(centroids=centroids)
        return df, centroids

    @staticmethod
    def get_optimal_clusters_number(df: pd.DataFrame,
                                    algorithm: Algorithm):
        wcss = []
        clustering_settings = algorithm.clustering_settings
        for i in range(1, clustering_settings.max_clusters + 1):
            k_means = KMeans(n_clusters=i,
                             init=clustering_settings.wcss_kmeans_init.value,
                             max_iter=clustering_settings.wcss_kmeans_max_iter,
                             n_init=clustering_settings.wcss_kmeans_n_init,
                             random_state=0)
            k_means.fit(df)
            wcss.append(k_means.inertia_)

        x = range(1, len(wcss) + 1)
        kn = KneeLocator(
            x, wcss, curve='convex', direction='decreasing',
            interp_method=clustering_settings.knee_interp_method.value,
            polynomial_degree=clustering_settings.knee_polynomial_degree)

        if kn.y_difference_maxima.shape[0] == 1 and \
                kn.y_difference_maxima <= 0.5 or not kn.knee:
            clusters_n = 1
        else:
            clusters_n = kn.knee
        return clusters_n

    @staticmethod
    def _preprocess(df: pd.DataFrame,
                    column_names=(COLUMN_CPU_LOAD, COLUMN_MEMORY_LOAD),
                    rolling_avg=2):
        df_ = df[list(column_names)].copy()
        for column_name in column_names:
            df_[column_name] = df_[column_name].rolling(
                window=rolling_avg, min_periods=1).mean()
        return df_

    @staticmethod
    def _convert_centroids(centroids: numpy.ndarray):
        centroids = centroids.tolist()
        result = []
        for centroid in centroids:
            centroid_ = [round(item, 2) for sublist in centroid
                         for item in sublist]
            result.append(centroid_)
        return result
