"""
Memory agent.

Provides agent-level workflows for storing observations,
recalling memories, retrieving memory records, forgetting records,
and generating memory summaries.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)


class MemoryAgent(AgentBase):
    """
    Agent responsible for memory workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "remember",
        "recall",
        "get-memory",
        "forget",
        "memory-summary",
        "pattern-memory",
        "trade-memory",
    }

    VALID_MEMORY_TYPES = {
        "observation",
        "pattern",
        "trade",
        "research",
        "strategy",
        "risk",
        "execution",
        "evaluation",
    }

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "memory-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for storing, recalling, forgetting, and summarizing AQOS memories."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a memory agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "remember":
            return self.remember(task)

        if task.action == "recall":
            return self.recall(task)

        if task.action == "get-memory":
            return self.get_memory(task)

        if task.action == "forget":
            return self.forget(task)

        if task.action == "memory-summary":
            return self.memory_summary(task)

        if task.action == "pattern-memory":
            return self.pattern_memory(task)

        if task.action == "trade-memory":
            return self.trade_memory(task)

        return self.failure(
            message=f"Unhandled memory agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return memory agent health.
        """

        return self.success(
            message="Memory agent is healthy.",
            data={
                "status": "ok",
                "records": len(self._records),
                "supported_memory_types": sorted(self.VALID_MEMORY_TYPES),
            },
            metadata=task.metadata,
        )

    def remember(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Store a memory record.
        """

        memory_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="memory_id",
            )
        )
        content = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="content",
            )
        )

        memory_type = str(
            task.payload.get(
                "memory_type",
                "observation",
            )
        ).lower()

        self._validate_memory_id(memory_id)
        self._validate_content(content)
        self._validate_memory_type(memory_type)

        importance = float(task.payload.get("importance", 0.5))
        self._validate_score(importance, "Importance")

        record = {
            "memory_id": memory_id,
            "content": content,
            "memory_type": memory_type,
            "importance": importance,
            "metadata": {
                **task.payload.get("metadata", {}),
                **task.metadata,
            },
        }

        self._records[memory_id] = deepcopy(record)

        return self.success(
            message="Memory stored.",
            data=deepcopy(record),
            metadata=task.metadata,
        )

    def recall(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Search memory records.
        """

        query = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="query",
            )
        )

        self._validate_query(query)

        limit = task.payload.get("limit")
        memory_type = task.payload.get("memory_type")

        if limit is not None:
            limit = int(limit)
            self._validate_limit(limit)

        if memory_type is not None:
            memory_type = str(memory_type).lower()
            self._validate_memory_type(memory_type)

        results = []

        for record in self._records.values():
            if memory_type is not None and record["memory_type"] != memory_type:
                continue

            score = self._score_record(
                query=query,
                record=record,
            )

            if score > 0:
                results.append(
                    {
                        "record": deepcopy(record),
                        "score": score,
                    }
                )

        results = sorted(
            results,
            key=lambda result: (
                result["score"],
                result["record"]["importance"],
            ),
            reverse=True,
        )

        if limit is not None:
            results = results[:limit]

        return self.success(
            message="Memory recall completed.",
            data={
                "query": query,
                "memory_type": memory_type,
                "results": results,
                "count": len(results),
            },
            metadata=task.metadata,
        )

    def get_memory(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Get a memory record by ID.
        """

        memory_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="memory_id",
            )
        )

        self._validate_memory_id(memory_id)

        record = self._records.get(memory_id)

        if record is None:
            return self.failure(
                message="Memory record does not exist.",
                metadata=task.metadata,
            )

        return self.success(
            message="Memory record retrieved.",
            data=deepcopy(record),
            metadata=task.metadata,
        )

    def forget(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Remove a memory record.
        """

        memory_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="memory_id",
            )
        )

        self._validate_memory_id(memory_id)

        existed = memory_id in self._records
        self._records.pop(memory_id, None)

        return self.success(
            message="Memory forget completed.",
            data={
                "memory_id": memory_id,
                "removed": existed,
            },
            metadata=task.metadata,
        )

    def memory_summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return memory summary.
        """

        counts_by_type = {
            memory_type: 0
            for memory_type in sorted(self.VALID_MEMORY_TYPES)
        }

        high_importance_records = 0

        for record in self._records.values():
            counts_by_type[record["memory_type"]] += 1

            if record["importance"] >= 0.7:
                high_importance_records += 1

        return self.success(
            message="Memory summary generated.",
            data={
                "records": len(self._records),
                "counts_by_type": counts_by_type,
                "high_importance_records": high_importance_records,
                "memory_ids": sorted(self._records.keys()),
            },
            metadata=task.metadata,
        )

    def pattern_memory(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Store a pattern memory record.
        """

        payload = {
            **task.payload,
            "memory_type": "pattern",
        }

        pattern = self.get_required_payload_value(
            payload=payload,
            key="pattern",
        )

        payload["content"] = str(
            payload.get(
                "content",
                f"Pattern observed: {pattern}",
            )
        )

        pattern_task = AgentTask(
            action="remember",
            payload=payload,
            metadata=task.metadata,
        )

        return self.remember(pattern_task)

    def trade_memory(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Store a trade memory record.
        """

        payload = {
            **task.payload,
            "memory_type": "trade",
        }

        symbol = str(
            self.get_required_payload_value(
                payload=payload,
                key="symbol",
            )
        )
        side = str(
            self.get_required_payload_value(
                payload=payload,
                key="side",
            )
        )
        outcome = str(
            self.get_required_payload_value(
                payload=payload,
                key="outcome",
            )
        )

        payload["content"] = str(
            payload.get(
                "content",
                f"Trade memory: {symbol.upper()} {side.lower()} outcome {outcome}.",
            )
        )

        trade_task = AgentTask(
            action="remember",
            payload=payload,
            metadata=task.metadata,
        )

        return self.remember(trade_task)

    def _score_record(
        self,
        query: str,
        record: dict[str, Any],
    ) -> float:
        """
        Score a record against a query.
        """

        query_terms = {
            term.lower()
            for term in query.split()
            if term.strip()
        }

        if not query_terms:
            return 0.0

        searchable_text = " ".join(
            [
                str(record["memory_id"]),
                str(record["content"]),
                str(record["memory_type"]),
                str(record["metadata"]),
            ]
        ).lower()

        matched_terms = [
            term
            for term in query_terms
            if term in searchable_text
        ]

        if not matched_terms:
            return 0.0

        return len(matched_terms) / len(query_terms)

    def _validate_memory_id(
        self,
        memory_id: str,
    ) -> None:
        """
        Validate memory ID.
        """

        if not memory_id:
            raise ValueError("Memory ID cannot be empty.")

    def _validate_content(
        self,
        content: str,
    ) -> None:
        """
        Validate memory content.
        """

        if not content:
            raise ValueError("Memory content cannot be empty.")

    def _validate_query(
        self,
        query: str,
    ) -> None:
        """
        Validate memory query.
        """

        if not query:
            raise ValueError("Memory query cannot be empty.")

    def _validate_memory_type(
        self,
        memory_type: str,
    ) -> None:
        """
        Validate memory type.
        """

        if memory_type not in self.VALID_MEMORY_TYPES:
            raise ValueError(
                "Memory type must be observation, pattern, trade, research, "
                "strategy, risk, execution, or evaluation."
            )

    def _validate_score(
        self,
        score: float,
        name: str,
    ) -> None:
        """
        Validate score between 0 and 1.
        """

        if score < 0 or score > 1:
            raise ValueError(f"{name} must be between 0.0 and 1.0.")

    def _validate_limit(
        self,
        limit: int,
    ) -> None:
        """
        Validate search limit.
        """

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")


__all__ = [
    "MemoryAgent",
]