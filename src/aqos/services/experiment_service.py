"""
Experiment service.

Provides a service-level interface for creating, tracking,
updating, and comparing AQOS experiment runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class ExperimentRun:
    """
    Represents an experiment run.
    """

    name: str
    status: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)


class ExperimentService:
    """
    Service layer for AQOS experiments.
    """

    VALID_STATUSES = {
        "created",
        "running",
        "completed",
        "failed",
    }

    def __init__(self) -> None:
        self._experiments: dict[str, ExperimentRun] = {}

    def create(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRun:
        """
        Create an experiment run.
        """

        self._validate_name(name)

        if name in self._experiments:
            raise ValueError("Experiment already exists.")

        experiment = ExperimentRun(
            name=name,
            status="created",
            description=description,
            metadata=metadata or {},
            results={},
        )

        self._experiments[name] = experiment

        return experiment

    def get(
        self,
        name: str,
    ) -> ExperimentRun | None:
        """
        Get an experiment by name.
        """

        self._validate_name(name)

        return self._experiments.get(name)

    def get_required(
        self,
        name: str,
    ) -> ExperimentRun:
        """
        Get an experiment or raise if it does not exist.
        """

        experiment = self.get(name)

        if experiment is None:
            raise ValueError("Experiment does not exist.")

        return experiment

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether an experiment exists.
        """

        self._validate_name(name)

        return name in self._experiments

    def list(self) -> list[ExperimentRun]:
        """
        Return all experiment runs.
        """

        return list(self._experiments.values())

    def list_names(self) -> list[str]:
        """
        Return experiment names.
        """

        return sorted(self._experiments.keys())

    def count(self) -> int:
        """
        Return the number of experiments.
        """

        return len(self._experiments)

    def update_status(
        self,
        name: str,
        status: str,
    ) -> ExperimentRun:
        """
        Update experiment status.
        """

        self._validate_status(status)

        experiment = self.get_required(name)

        updated = ExperimentRun(
            name=experiment.name,
            status=status,
            description=experiment.description,
            metadata=dict(experiment.metadata),
            results=dict(experiment.results),
        )

        self._experiments[name] = updated

        return updated

    def start(
        self,
        name: str,
    ) -> ExperimentRun:
        """
        Mark an experiment as running.
        """

        return self.update_status(
            name=name,
            status="running",
        )

    def complete(
        self,
        name: str,
    ) -> ExperimentRun:
        """
        Mark an experiment as completed.
        """

        return self.update_status(
            name=name,
            status="completed",
        )

    def fail(
        self,
        name: str,
        reason: str,
    ) -> ExperimentRun:
        """
        Mark an experiment as failed.
        """

        if not reason:
            raise ValueError("Failure reason cannot be empty.")

        experiment = self.add_result(
            name=name,
            key="failure_reason",
            value=reason,
        )

        return self.update_status(
            name=experiment.name,
            status="failed",
        )

    def add_result(
        self,
        name: str,
        key: str,
        value: Any,
    ) -> ExperimentRun:
        """
        Add or update an experiment result.
        """

        self._validate_result_key(key)

        experiment = self.get_required(name)

        results = dict(experiment.results)
        results[key] = value

        updated = ExperimentRun(
            name=experiment.name,
            status=experiment.status,
            description=experiment.description,
            metadata=dict(experiment.metadata),
            results=results,
        )

        self._experiments[name] = updated

        return updated

    def remove(
        self,
        name: str,
    ) -> None:
        """
        Remove an experiment.
        """

        self._validate_name(name)

        self._experiments.pop(name, None)

    def clear(self) -> None:
        """
        Clear all experiments.
        """

        self._experiments.clear()

    def best_by_metric(
        self,
        metric: str,
        higher_is_better: bool = True,
    ) -> ExperimentRun:
        """
        Return the best experiment by a numeric metric.
        """

        self._validate_result_key(metric)

        if not self._experiments:
            raise ValueError("No experiments are available.")

        candidates = [
            experiment
            for experiment in self._experiments.values()
            if metric in experiment.results
        ]

        if not candidates:
            raise ValueError("No experiments contain the requested metric.")

        return max(
            candidates,
            key=lambda experiment: experiment.results[metric],
        ) if higher_is_better else min(
            candidates,
            key=lambda experiment: experiment.results[metric],
        )

    def _validate_name(
        self,
        name: str,
    ) -> None:
        """
        Validate experiment name.
        """

        if not name:
            raise ValueError("Experiment name cannot be empty.")

    def _validate_status(
        self,
        status: str,
    ) -> None:
        """
        Validate experiment status.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                "Experiment status must be created, running, "
                "completed, or failed."
            )

    def _validate_result_key(
        self,
        key: str,
    ) -> None:
        """
        Validate result key.
        """

        if not key:
            raise ValueError("Result key cannot be empty.")


__all__ = [
    "ExperimentRun",
    "ExperimentService",
]