from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


VALID_SIGNAL_LABELS = {"buy", "sell", "hold"}


@dataclass(frozen=True)
class SignalModelTrainingConfig:
    target_column: str = "target"
    test_size: float = 0.25
    random_state: int = 42
    n_estimators: int = 100
    max_depth: int | None = 6
    min_samples_leaf: int = 1


@dataclass(frozen=True)
class SignalModelTrainingResult:
    model_name: str
    target_column: str
    feature_columns: tuple[str, ...]
    train_rows: int
    test_rows: int
    labels: tuple[str, ...]
    accuracy: float
    classification_report: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "target_column": self.target_column,
            "feature_columns": list(self.feature_columns),
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "labels": list(self.labels),
            "accuracy": self.accuracy,
            "classification_report": self.classification_report,
        }


class BaselineSignalModel:
    """
    Real baseline AQOS signal model.

    This model is intentionally simple and production-friendly:
    - uses sklearn RandomForestClassifier
    - accepts engineered trading features
    - predicts buy/sell/hold labels
    - supports probability output
    - supports joblib persistence
    """

    def __init__(
        self,
        config: SignalModelTrainingConfig | None = None,
    ) -> None:
        self.config = config or SignalModelTrainingConfig()
        self.model_name = "baseline_random_forest_signal_model"
        self.feature_columns: tuple[str, ...] = ()
        self.labels: tuple[str, ...] = ()
        self.pipeline: Pipeline | None = None
        self.training_result: SignalModelTrainingResult | None = None

    @property
    def is_trained(self) -> bool:
        return self.pipeline is not None and bool(self.feature_columns)

    def train(
        self,
        dataset: pd.DataFrame,
        feature_columns: list[str] | tuple[str, ...] | None = None,
    ) -> SignalModelTrainingResult:
        self._validate_dataset(dataset)

        resolved_features = self._resolve_feature_columns(dataset, feature_columns)
        X = dataset.loc[:, list(resolved_features)]
        y = dataset[self.config.target_column].astype(str).str.lower()

        self._validate_labels(y)

        stratify = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.config.test_size,
            random_state=self.config.random_state,
            stratify=stratify,
        )

        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=self.config.n_estimators,
                        max_depth=self.config.max_depth,
                        min_samples_leaf=self.config.min_samples_leaf,
                        random_state=self.config.random_state,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

        pipeline.fit(X_train, y_train)
        predictions = pipeline.predict(X_test)

        labels = tuple(sorted(y.unique()))

        result = SignalModelTrainingResult(
            model_name=self.model_name,
            target_column=self.config.target_column,
            feature_columns=tuple(resolved_features),
            train_rows=len(X_train),
            test_rows=len(X_test),
            labels=labels,
            accuracy=float(accuracy_score(y_test, predictions)),
            classification_report=classification_report(
                y_test,
                predictions,
                labels=list(labels),
                output_dict=True,
                zero_division=0,
            ),
        )

        self.pipeline = pipeline
        self.feature_columns = tuple(resolved_features)
        self.labels = labels
        self.training_result = result

        return result

    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        self._validate_trained()
        prepared = self._prepare_features(features)
        predictions = self.pipeline.predict(prepared)  # type: ignore[union-attr]
        return pd.Series(predictions, index=features.index, name="predicted_signal")

    def predict_proba(
        self,
        features: pd.DataFrame,
    ) -> pd.DataFrame:
        self._validate_trained()
        prepared = self._prepare_features(features)

        classifier = self.pipeline.named_steps["classifier"]  # type: ignore[union-attr]
        probabilities = self.pipeline.predict_proba(prepared)  # type: ignore[union-attr]
        columns = [f"probability_{label}" for label in classifier.classes_]

        return pd.DataFrame(probabilities, index=features.index, columns=columns)

    def save(
        self,
        path: str | Path,
    ) -> Path:
        self._validate_trained()

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model_name": self.model_name,
            "config": self.config,
            "feature_columns": self.feature_columns,
            "labels": self.labels,
            "pipeline": self.pipeline,
            "training_result": self.training_result,
        }

        joblib.dump(payload, output_path)
        return output_path

    @classmethod
    def load(
        cls,
        path: str | Path,
    ) -> "BaselineSignalModel":
        payload = joblib.load(Path(path))

        model = cls(config=payload["config"])
        model.model_name = payload["model_name"]
        model.feature_columns = tuple(payload["feature_columns"])
        model.labels = tuple(payload["labels"])
        model.pipeline = payload["pipeline"]
        model.training_result = payload["training_result"]

        return model

    def _validate_dataset(
        self,
        dataset: pd.DataFrame,
    ) -> None:
        if dataset.empty:
            raise ValueError("Training dataset cannot be empty.")

        if self.config.target_column not in dataset.columns:
            raise ValueError(
                f"Training dataset must contain target column: {self.config.target_column}"
            )

        if len(dataset) < 8:
            raise ValueError("Training dataset must contain at least 8 rows.")

    def _resolve_feature_columns(
        self,
        dataset: pd.DataFrame,
        feature_columns: list[str] | tuple[str, ...] | None,
    ) -> tuple[str, ...]:
        if feature_columns is None:
            resolved = tuple(
                column
                for column in dataset.columns
                if column != self.config.target_column
                and pd.api.types.is_numeric_dtype(dataset[column])
            )
        else:
            resolved = tuple(feature_columns)

        if not resolved:
            raise ValueError("At least one numeric feature column is required.")

        missing = [column for column in resolved if column not in dataset.columns]
        if missing:
            raise ValueError(f"Feature columns are missing from dataset: {missing}")

        non_numeric = [
            column
            for column in resolved
            if not pd.api.types.is_numeric_dtype(dataset[column])
        ]
        if non_numeric:
            raise ValueError(f"Feature columns must be numeric: {non_numeric}")

        return resolved

    def _validate_labels(
        self,
        labels: pd.Series,
    ) -> None:
        unique_labels = set(labels.unique())

        unknown = sorted(unique_labels - VALID_SIGNAL_LABELS)
        if unknown:
            raise ValueError(
                f"Unsupported signal labels: {unknown}. "
                f"Valid labels are: {sorted(VALID_SIGNAL_LABELS)}"
            )

        if len(unique_labels) < 2:
            raise ValueError("Training dataset must contain at least two signal classes.")

    def _validate_trained(
        self,
    ) -> None:
        if not self.is_trained or self.pipeline is None:
            raise RuntimeError("BaselineSignalModel must be trained or loaded before prediction.")

    def _prepare_features(
        self,
        features: pd.DataFrame,
    ) -> pd.DataFrame:
        missing = [column for column in self.feature_columns if column not in features.columns]
        if missing:
            raise ValueError(f"Prediction features are missing required columns: {missing}")

        return features.loc[:, list(self.feature_columns)]


__all__ = [
    "BaselineSignalModel",
    "SignalModelTrainingConfig",
    "SignalModelTrainingResult",
    "VALID_SIGNAL_LABELS",
]