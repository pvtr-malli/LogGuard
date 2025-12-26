"""
Anomaly prediction module for log anomaly detection.

This module loads trained models and makes predictions on extracted features.
"""

import pandas as pd
import numpy as np
import pickle
from typing import Tuple
from pathlib import Path


class AnomalyPredictor:
    """
    Make anomaly predictions using trained DBSCAN model.
    """

    def __init__(self, model_path: str, scaler_path: str):
        """
        Initialize predictor with trained model and scaler.

        param model_path: Path to saved DBSCAN model pickle file.
        param scaler_path: Path to saved StandardScaler pickle file.
        """
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)

        # Load model and scaler.
        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)

        with open(self.scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Make anomaly predictions on extracted features.

        param features_df: DataFrame with extracted features.
        """
        # Remove timestamp column if present.
        if 'timestamp' in features_df.columns:
            timestamps = features_df['timestamp']
            features_df = features_df.drop(columns=['timestamp'])
        else:
            timestamps = None

        # Scale features.
        X_scaled = self.scaler.transform(features_df)

        # Predict using DBSCAN (noise points are anomalies).
        labels = self.model.fit_predict(X_scaled)

        # Convert to binary anomaly flag (1 = anomaly, 0 = normal).
        anomaly_flags = (labels == -1).astype(int)

        # Create results DataFrame.
        results = pd.DataFrame({
            'is_anomaly': anomaly_flags
        })

        if timestamps is not None:
            results.insert(0, 'timestamp', timestamps)

        return results

    def predict_with_confidence(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Make predictions with anomaly confidence scores.

        param features_df: DataFrame with extracted features.
        """
        # Remove timestamp column if present.
        if 'timestamp' in features_df.columns:
            timestamps = features_df['timestamp']
            features_df = features_df.drop(columns=['timestamp'])
        else:
            timestamps = None

        # Scale features.
        X_scaled = self.scaler.transform(features_df)

        # Predict using DBSCAN.
        labels = self.model.fit_predict(X_scaled)

        # Convert to binary anomaly flag.
        anomaly_flags = (labels == -1).astype(int)

        # Calculate anomaly confidence scores.
        # For DBSCAN, use distance to nearest cluster centroid.
        cluster_centers = self._compute_cluster_centers(X_scaled, labels)
        anomaly_scores = self._compute_anomaly_scores(X_scaled, labels, cluster_centers)

        # Create results DataFrame.
        results = pd.DataFrame({
            'is_anomaly': anomaly_flags,
            'anomaly_score': anomaly_scores,
            'cluster_label': labels
        })

        if timestamps is not None:
            results.insert(0, 'timestamp', timestamps)

        return results

    def _compute_cluster_centers(self, X_scaled: np.ndarray, labels: np.ndarray) -> dict:
        """
        Compute centroids for each cluster.

        param X_scaled: Scaled feature matrix.
        param labels: Cluster labels from DBSCAN.
        """
        cluster_centers = {}
        unique_labels = set(labels)

        # Remove noise label (-1).
        unique_labels.discard(-1)

        for label in unique_labels:
            cluster_mask = labels == label
            cluster_centers[label] = X_scaled[cluster_mask].mean(axis=0)

        return cluster_centers

    def _compute_anomaly_scores(
        self,
        X_scaled: np.ndarray,
        labels: np.ndarray,
        cluster_centers: dict
    ) -> np.ndarray:
        """
        Compute anomaly scores based on distance to cluster centers.

        param X_scaled: Scaled feature matrix.
        param labels: Cluster labels from DBSCAN.
        param cluster_centers: Dictionary of cluster centroids.
        """
        anomaly_scores = np.zeros(len(X_scaled))

        for i in range(len(X_scaled)):
            if labels[i] == -1:
                # Noise point: distance to nearest cluster center.
                if cluster_centers:
                    min_dist = min(
                        np.linalg.norm(X_scaled[i] - center)
                        for center in cluster_centers.values()
                    )
                    anomaly_scores[i] = min_dist
                else:
                    anomaly_scores[i] = 1.0
            else:
                # Normal point: distance to its own cluster center.
                center = cluster_centers[labels[i]]
                anomaly_scores[i] = np.linalg.norm(X_scaled[i] - center)

        # Normalize scores to [0, 1].
        if anomaly_scores.max() > 0:
            anomaly_scores = anomaly_scores / anomaly_scores.max()

        return anomaly_scores
