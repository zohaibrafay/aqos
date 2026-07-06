"""
Learning pipeline.

Coordinates the learning components used during model training.

The implementation is intentionally lightweight in Sprint 006.
Future sprints will extend this pipeline with real machine learning
frameworks, experiment tracking, checkpointing, distributed training,
and hyperparameter optimization.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aqos.learning.cross_validation import CrossValidation
from aqos.learning.loss import Loss
from aqos.learning.optimizer import Optimizer
from aqos.learning.scheduler import Scheduler
from aqos.learning.trainer import Trainer


@dataclass(slots=True)
class LearningPipeline:
    """
    Learning pipeline.
    """

    trainer: Trainer
    optimizer: Optimizer
    scheduler: Scheduler
    loss: Loss
    cross_validation: CrossValidation

    def run(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ):
        """
        Execute the learning pipeline.

        Parameters
        ----------
        features : pd.DataFrame
            Training features.

        target : pd.Series
            Training targets.

        Returns
        -------
        BaseModel
            Trained model.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        if target.empty:
            raise ValueError("Target cannot be empty.")

        if len(features) != len(target):
            raise ValueError(
                "Features and target must have the same length."
            )

        self.optimizer.validate()
        self.scheduler.validate()
        self.loss.validate()
        self.cross_validation.validate()

        return self.trainer.train(
            features=features,
            target=target,
        )


__all__ = ["LearningPipeline"]