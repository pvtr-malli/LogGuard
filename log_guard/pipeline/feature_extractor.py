"""
Feature extraction module for log anomaly detection.

This module extracts volume, rolling statistics, and text features from logs.
"""

import pandas as pd
import numpy as np
import re
from typing import Dict
from sklearn.metrics import pairwise_distances


class FeatureExtractor:
    """
    Extract features from logs for anomaly detection.
    """

    def __init__(self, tfidf, svd, kmeans, message_rarity_lookup: Dict[str, float]):
        """
        Initialize feature extractor.

        param tfidf: Fitted TF-IDF vectorizer.
        param svd: Fitted TruncatedSVD reducer.
        param kmeans: Fitted KMeans clustering model.
        param message_rarity_lookup: Dictionary mapping messages to rarity scores.
        """
        self.tfidf = tfidf
        self.svd = svd
        self.kmeans = kmeans
        self.message_rarity_lookup = message_rarity_lookup

    @staticmethod
    def preprocess_log_message(message: str) -> str:
        """
        Preprocess log message for embedding.

        param message: Raw log message.
        """
        message = message.lower()
        message = re.sub(r'\d+', '<NUM>', message)
        message = re.sub(r'user_\d+', 'user_<ID>', message)
        message = re.sub(r'session_\d+', 'session_<ID>', message)
        message = re.sub(r'txn_\d+', 'txn_<ID>', message)
        message = re.sub(r'ord_\d+', 'ord_<ID>', message)
        message = re.sub(r'item_\d+', 'item_<ID>', message)
        message = re.sub(r'cache_\d+', 'cache_<ID>', message)
        message = re.sub(r'\d+ms', '<DURATION>ms', message)
        message = re.sub(r'\d+s', '<DURATION>s', message)
        message = re.sub(r'\d+\.\d+\.\d+\.\d+', '<IP>', message)
        message = re.sub(r'/[\w/]+', '<PATH>', message)
        return message.strip()

    def extract_volume_features(self, df: pd.DataFrame, window: str = '30s') -> pd.DataFrame:
        """
        Extract volume and frequency features.

        param df: DataFrame with columns [timestamp, level].
        param window: Time window for aggregation.
        """
        df_indexed = df.set_index('timestamp')

        # Binary indicators for log levels.
        df_indexed['is_error'] = (df_indexed['level'] == 'ERROR').astype(int)
        df_indexed['is_fatal'] = (df_indexed['level'] == 'FATAL').astype(int)
        df_indexed['is_warn'] = (df_indexed['level'] == 'WARN').astype(int)
        df_indexed['is_info'] = (df_indexed['level'] == 'INFO').astype(int)
        df_indexed['is_debug'] = (df_indexed['level'] == 'DEBUG').astype(int)

        # Aggregate per window.
        window_features = df_indexed.resample(window).agg({
            'level': 'count',
            'is_error': 'sum',
            'is_fatal': 'sum',
            'is_warn': 'sum',
            'is_info': 'sum',
            'is_debug': 'sum'
        })

        window_features.columns = ['log_count', 'error_count', 'fatal_count',
                                     'warn_count', 'info_count', 'debug_count']

        # Derived rates.
        window_features['error_rate'] = window_features['error_count'] / window_features['log_count'].replace(0, 1)
        window_features['fatal_rate'] = window_features['fatal_count'] / window_features['log_count'].replace(0, 1)
        window_features['warn_rate'] = window_features['warn_count'] / window_features['log_count'].replace(0, 1)
        window_features['warn_to_info_ratio'] = window_features['warn_count'] / window_features['info_count'].replace(0, 1)
        window_features['critical_count'] = window_features['error_count'] + window_features['fatal_count']
        window_features['critical_rate'] = window_features['critical_count'] / window_features['log_count'].replace(0, 1)

        return window_features

    def extract_text_features(self, df: pd.DataFrame, window: str = '30s') -> pd.DataFrame:
        """
        Extract text embedding and clustering features.

        param df: DataFrame with columns [timestamp, message].
        param window: Time window for aggregation.
        """
        df['message_processed'] = df['message'].apply(self.preprocess_log_message)
        tfidf_matrix = self.tfidf.transform(df['message_processed'])
        tfidf_reduced = self.svd.transform(tfidf_matrix)
        df['message_cluster'] = self.kmeans.predict(tfidf_reduced)

        # Message anomaly score (distance to centroid).
        distances = pairwise_distances(tfidf_reduced, self.kmeans.cluster_centers_, metric='euclidean')
        df['message_distance'] = distances[np.arange(len(df)), df['message_cluster']]
        # normalize to get teh score.
        min_dist = df['message_distance'].min()
        max_dist = df['message_distance'].max()
        df['message_anomaly_score'] = (df['message_distance'] - min_dist) / (max_dist - min_dist + 1e-10)

        df['message_rarity'] = df['message_processed'].map(self.message_rarity_lookup).fillna(1.0)
        for i in range(15):
            df[f'tfidf_{i}'] = tfidf_reduced[:, i]

        # Aggregate text features per window.
        df_text_indexed = df.set_index('timestamp')
        text_cols = ['message_rarity', 'message_anomaly_score', 'message_cluster'] + [f'tfidf_{i}' for i in range(15)]
        text_features = df_text_indexed[text_cols].resample(window).mean()

        return text_features

    def extract_all_features(self, df: pd.DataFrame, window: str = '30s') -> pd.DataFrame:
        """
        Extract all features from logs.

        param df: DataFrame with columns [timestamp, level, message].
        param window: Time window for aggregation.
        """
        # Ensure timestamp is datetime.
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 1. Volume features.
        volume_features = self.extract_volume_features(df, window)

        # 3. Text features.
        text_features = self.extract_text_features(df, window)

        # Merge features.
        all_features = volume_features.join(text_features, how='left')

        # Fill NaNs and infinities.
        all_features = all_features.fillna(0).replace([np.inf, -np.inf], 0)

        return all_features.reset_index()
