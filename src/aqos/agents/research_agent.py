"""
Research agent.

Provides agent-level workflows for hypothesis generation,
experiment planning, finding storage, and research summaries.
"""

from __future__ import annotations

from typing import Any

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.services import (
    ExperimentService,
    StorageService,
)


class ResearchAgent(AgentBase):
    """
    Agent responsible for research workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "hypothesis",
        "experiment-plan",
        "create-experiment",
        "record-finding",
        "research-summary",
    }

    RESEARCH_NAMESPACE = "research"

    def __init__(
        self,
        experiment_service: ExperimentService | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self._experiment_service = experiment_service or ExperimentService()
        self._storage_service = storage_service or StorageService()
        self._findings: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "research-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for hypotheses, experiment planning, and research findings."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a research agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "hypothesis":
            return self.hypothesis(task)

        if task.action == "experiment-plan":
            return self.experiment_plan(task)

        if task.action == "create-experiment":
            return self.create_experiment(task)

        if task.action == "record-finding":
            return self.record_finding(task)

        if task.action == "research-summary":
            return self.research_summary(task)

        return self.failure(
            message=f"Unhandled research agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return research agent health.
        """

        return self.success(
            message="Research agent is healthy.",
            data={
                "status": "ok",
                "experiments": self._experiment_service.count(),
                "findings": len(self._findings),
            },
            metadata=task.metadata,
        )

    def hypothesis(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Generate a simple research hypothesis.
        """

        symbol = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="symbol",
            )
        )
        signal_source = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="signal_source",
            )
        )

        timeframe = str(task.payload.get("timeframe", "H1"))
        objective = str(task.payload.get("objective", "improve signal quality"))

        hypothesis_text = (
            f"{signal_source} may improve {symbol.upper()} {timeframe.upper()} "
            f"decision quality by helping AQOS {objective}."
        )

        return self.success(
            message="Research hypothesis generated.",
            data={
                "symbol": symbol.upper(),
                "timeframe": timeframe.upper(),
                "signal_source": signal_source,
                "objective": objective,
                "hypothesis": hypothesis_text,
            },
            metadata=task.metadata,
        )

    def experiment_plan(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Build a research experiment plan.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )
        hypothesis = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="hypothesis",
            )
        )

        symbol = str(task.payload.get("symbol", "UNKNOWN")).upper()
        timeframe = str(task.payload.get("timeframe", "H1")).upper()
        metric = str(task.payload.get("metric", "win_rate"))

        steps = [
            "Prepare historical OHLCV dataset.",
            "Generate baseline strategy results.",
            "Apply proposed research hypothesis.",
            "Run backtest on the same dataset.",
            "Compare results against baseline metrics.",
            "Record finding and recommendation.",
        ]

        return self.success(
            message="Research experiment plan generated.",
            data={
                "name": name,
                "symbol": symbol,
                "timeframe": timeframe,
                "hypothesis": hypothesis,
                "metric": metric,
                "steps": steps,
            },
            metadata=task.metadata,
        )

    def create_experiment(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Create an experiment through ExperimentService.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )

        description = str(task.payload.get("description", ""))
        metadata = {
            **task.payload.get("metadata", {}),
            **task.metadata,
        }

        try:
            experiment = self._experiment_service.create(
                name=name,
                description=description,
                metadata=metadata,
            )

            return self.success(
                message="Research experiment created.",
                data={
                    "name": experiment.name,
                    "status": experiment.status,
                    "description": experiment.description,
                    "metadata": experiment.metadata,
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def record_finding(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Record a research finding.
        """

        finding_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="finding_id",
            )
        )
        title = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="title",
            )
        )
        conclusion = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="conclusion",
            )
        )

        confidence = float(task.payload.get("confidence", 0.0))

        self._validate_confidence(confidence)

        record = {
            "finding_id": finding_id,
            "title": title,
            "conclusion": conclusion,
            "confidence": confidence,
            "metadata": task.payload.get("metadata", {}),
        }

        self._findings[finding_id] = record

        self._storage_service.save(
            key=finding_id,
            value=record,
            namespace=self.RESEARCH_NAMESPACE,
        )

        return self.success(
            message="Research finding recorded.",
            data=record,
            metadata=task.metadata,
        )

    def research_summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return research summary.
        """

        findings = list(self._findings.values())

        high_confidence_findings = [
            finding
            for finding in findings
            if finding["confidence"] >= 0.7
        ]

        return self.success(
            message="Research summary generated.",
            data={
                "experiments": self._experiment_service.count(),
                "findings": len(findings),
                "high_confidence_findings": len(high_confidence_findings),
                "finding_ids": sorted(self._findings.keys()),
            },
            metadata=task.metadata,
        )

    def _validate_confidence(
        self,
        confidence: float,
    ) -> None:
        """
        Validate research confidence score.
        """

        if confidence < 0 or confidence > 1:
            raise ValueError("Confidence must be between 0.0 and 1.0.")


__all__ = [
    "ResearchAgent",
]