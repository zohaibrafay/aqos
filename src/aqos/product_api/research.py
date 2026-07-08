"""
AQOS product-facing research API.

This module provides dependency-free product API primitives for research
requests, findings, reports, summaries, stores, and response helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.product_api.base import (
    ProductApiErrorCode,
    ProductApiRequestContext,
    ProductApiResponse,
    product_api_failure,
    product_api_success,
    validate_metadata,
    validate_non_empty_string,
    validate_percentage,
    validate_product_symbol,
    validate_product_timeframe,
    validate_string,
)
from aqos.product_api.contracts import (
    ProductApiListQuery,
    ProductApiListResult,
    ProductApiOperation,
    ProductApiOperationResult,
    ProductApiPagination,
    ProductApiRequestType,
    list_result_to_response,
    operation_result_to_response,
)


class ProductResearchStatus(str, Enum):
    """Supported product research statuses."""

    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProductResearchPriority(str, Enum):
    """Supported product research priorities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProductResearchFindingType(str, Enum):
    """Supported product research finding types."""

    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    BACKTEST = "backtest"
    MARKET_NOTE = "market_note"
    RISK_NOTE = "risk_note"


@dataclass(frozen=True)
class ProductResearchRequest:
    """Product research request."""

    topic: str
    symbol: str = ""
    timeframe: str = ""
    priority: ProductResearchPriority | str = ProductResearchPriority.MEDIUM
    tags: list[str] = field(default_factory=list)
    include_sources: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.topic, "Topic")

        if self.symbol:
            validate_product_symbol(self.symbol)

        if self.timeframe:
            validate_product_timeframe(self.timeframe)

        normalize_product_research_priority(self.priority)
        validate_research_tags(self.tags)

        if not isinstance(self.include_sources, bool):
            raise ValueError("Include sources must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert research request into dictionary."""
        return {
            "topic": self.topic.strip(),
            "symbol": validate_product_symbol(self.symbol) if self.symbol else "",
            "timeframe": validate_product_timeframe(self.timeframe) if self.timeframe else "",
            "priority": normalize_product_research_priority(self.priority).value,
            "tags": [tag.strip() for tag in self.tags],
            "include_sources": self.include_sources,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductResearchFinding:
    """Product-facing research finding."""

    finding_id: str
    title: str
    finding_type: ProductResearchFindingType | str
    summary: str
    confidence: float
    priority: ProductResearchPriority | str = ProductResearchPriority.MEDIUM
    status: ProductResearchStatus | str = ProductResearchStatus.DRAFT
    symbol: str = ""
    timeframe: str = ""
    tags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.finding_id, "Finding ID")
        validate_non_empty_string(self.title, "Title")
        normalize_product_research_finding_type(self.finding_type)
        validate_non_empty_string(self.summary, "Summary")
        validate_percentage(self.confidence, "Confidence")
        normalize_product_research_priority(self.priority)
        normalize_product_research_status(self.status)

        if self.symbol:
            validate_product_symbol(self.symbol)

        if self.timeframe:
            validate_product_timeframe(self.timeframe)

        validate_research_tags(self.tags)
        validate_metadata(self.evidence, "Evidence")
        validate_metadata(self.metadata, "Metadata")
        validate_non_empty_string(self.created_at, "Created at")

    @property
    def completed(self) -> bool:
        """Return whether finding is completed."""
        return normalize_product_research_status(self.status) == ProductResearchStatus.COMPLETED

    @property
    def high_priority(self) -> bool:
        """Return whether finding is high priority."""
        return normalize_product_research_priority(self.priority) in {
            ProductResearchPriority.HIGH,
            ProductResearchPriority.CRITICAL,
        }

    @property
    def actionable(self) -> bool:
        """Return whether finding is actionable."""
        return self.completed and self.high_priority and self.confidence >= 60

    def to_dict(self) -> dict[str, Any]:
        """Convert research finding into dictionary."""
        return {
            "finding_id": self.finding_id.strip(),
            "title": self.title.strip(),
            "finding_type": normalize_product_research_finding_type(self.finding_type).value,
            "summary": self.summary.strip(),
            "confidence": float(self.confidence),
            "priority": normalize_product_research_priority(self.priority).value,
            "status": normalize_product_research_status(self.status).value,
            "symbol": validate_product_symbol(self.symbol) if self.symbol else "",
            "timeframe": validate_product_timeframe(self.timeframe) if self.timeframe else "",
            "tags": [tag.strip() for tag in self.tags],
            "evidence": dict(self.evidence),
            "metadata": dict(self.metadata),
            "completed": self.completed,
            "high_priority": self.high_priority,
            "actionable": self.actionable,
            "created_at": self.created_at.strip(),
        }


@dataclass(frozen=True)
class ProductResearchSummary:
    """Compact product research summary."""

    total: int = 0
    draft: int = 0
    running: int = 0
    completed: int = 0
    archived: int = 0
    high_priority: int = 0
    average_confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.total, "Total")
        validate_non_negative_integer(self.draft, "Draft")
        validate_non_negative_integer(self.running, "Running")
        validate_non_negative_integer(self.completed, "Completed")
        validate_non_negative_integer(self.archived, "Archived")
        validate_non_negative_integer(self.high_priority, "High priority")
        validate_percentage(self.average_confidence, "Average confidence")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert research summary into dictionary."""
        return {
            "total": self.total,
            "draft": self.draft,
            "running": self.running,
            "completed": self.completed,
            "archived": self.archived,
            "high_priority": self.high_priority,
            "average_confidence": float(self.average_confidence),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductResearchReport:
    """Product-facing research report."""

    report_id: str
    title: str
    findings: list[ProductResearchFinding] = field(default_factory=list)
    summary: str = ""
    status: ProductResearchStatus | str = ProductResearchStatus.COMPLETED
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.report_id, "Report ID")
        validate_non_empty_string(self.title, "Title")
        validate_product_research_findings(self.findings)
        validate_string(self.summary, "Summary")
        normalize_product_research_status(self.status)
        validate_metadata(self.metadata, "Metadata")
        validate_non_empty_string(self.generated_at, "Generated at")

    def to_dict(self) -> dict[str, Any]:
        """Convert research report into dictionary."""
        return {
            "report_id": self.report_id.strip(),
            "title": self.title.strip(),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary.strip(),
            "status": normalize_product_research_status(self.status).value,
            "research_summary": summarize_product_research_findings(self.findings).to_dict(),
            "metadata": dict(self.metadata),
            "generated_at": self.generated_at.strip(),
        }


@dataclass
class ProductResearchStore:
    """In-memory product research store."""

    findings: dict[str, ProductResearchFinding] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.findings, dict):
            raise ValueError("Findings must be a dictionary.")

        for finding_id, finding in self.findings.items():
            validate_non_empty_string(finding_id, "Finding ID")

            if not isinstance(finding, ProductResearchFinding):
                raise ValueError("Findings must contain ProductResearchFinding objects.")

    def add(self, finding: ProductResearchFinding) -> ProductResearchFinding:
        """Add finding to store."""
        if not isinstance(finding, ProductResearchFinding):
            raise ValueError("Finding must be a ProductResearchFinding.")

        self.findings[finding.finding_id.strip()] = finding
        return finding

    def get(self, finding_id: str) -> ProductResearchFinding | None:
        """Get finding by ID."""
        normalized_finding_id = validate_non_empty_string(finding_id, "Finding ID")
        return self.findings.get(normalized_finding_id)

    def list(self) -> list[ProductResearchFinding]:
        """List findings."""
        return list(self.findings.values())

    def remove(self, finding_id: str) -> ProductResearchFinding | None:
        """Remove finding by ID."""
        normalized_finding_id = validate_non_empty_string(finding_id, "Finding ID")
        return self.findings.pop(normalized_finding_id, None)

    def clear(self) -> None:
        """Clear research store."""
        self.findings.clear()

    def count(self) -> int:
        """Return finding count."""
        return len(self.findings)


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_research_tags(tags: list[str]) -> list[str]:
    """Validate research tags."""
    if not isinstance(tags, list):
        raise ValueError("Tags must be a list.")

    for tag in tags:
        validate_non_empty_string(tag, "Tag")

    return tags


def normalize_product_research_status(
    status: ProductResearchStatus | str,
) -> ProductResearchStatus:
    """Normalize product research status."""
    if isinstance(status, ProductResearchStatus):
        return status

    normalized = validate_non_empty_string(status, "Research status").lower()

    try:
        return ProductResearchStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductResearchStatus)
        raise ValueError(
            f"Invalid research status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_product_research_priority(
    priority: ProductResearchPriority | str,
) -> ProductResearchPriority:
    """Normalize product research priority."""
    if isinstance(priority, ProductResearchPriority):
        return priority

    normalized = validate_non_empty_string(priority, "Research priority").lower()

    try:
        return ProductResearchPriority(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductResearchPriority)
        raise ValueError(
            f"Invalid research priority '{priority}'. Valid priorities: {valid}.",
        ) from exc


def normalize_product_research_finding_type(
    finding_type: ProductResearchFindingType | str,
) -> ProductResearchFindingType:
    """Normalize product research finding type."""
    if isinstance(finding_type, ProductResearchFindingType):
        return finding_type

    normalized = validate_non_empty_string(finding_type, "Research finding type").lower()

    try:
        return ProductResearchFindingType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductResearchFindingType)
        raise ValueError(
            f"Invalid research finding type '{finding_type}'. Valid finding types: {valid}.",
        ) from exc


def build_product_research_request(
    *,
    topic: str,
    symbol: str = "",
    timeframe: str = "",
    priority: ProductResearchPriority | str = ProductResearchPriority.MEDIUM,
    tags: list[str] | None = None,
    include_sources: bool = True,
    metadata: dict[str, Any] | None = None,
) -> ProductResearchRequest:
    """Build product research request."""
    return ProductResearchRequest(
        topic=topic,
        symbol=symbol,
        timeframe=timeframe,
        priority=priority,
        tags=tags or [],
        include_sources=include_sources,
        metadata=metadata or {},
    )


def build_product_research_finding(
    *,
    finding_id: str,
    title: str,
    finding_type: ProductResearchFindingType | str,
    summary: str,
    confidence: float,
    priority: ProductResearchPriority | str = ProductResearchPriority.MEDIUM,
    status: ProductResearchStatus | str = ProductResearchStatus.DRAFT,
    symbol: str = "",
    timeframe: str = "",
    tags: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> ProductResearchFinding:
    """Build product research finding."""
    finding_kwargs: dict[str, Any] = {
        "finding_id": finding_id,
        "title": title,
        "finding_type": finding_type,
        "summary": summary,
        "confidence": confidence,
        "priority": priority,
        "status": status,
        "symbol": symbol,
        "timeframe": timeframe,
        "tags": tags or [],
        "evidence": evidence or {},
        "metadata": metadata or {},
    }

    if created_at is not None:
        finding_kwargs["created_at"] = created_at

    return ProductResearchFinding(**finding_kwargs)


def build_product_research_report(
    *,
    report_id: str,
    title: str,
    findings: list[ProductResearchFinding] | None = None,
    summary: str = "",
    status: ProductResearchStatus | str = ProductResearchStatus.COMPLETED,
    metadata: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> ProductResearchReport:
    """Build product research report."""
    report_kwargs: dict[str, Any] = {
        "report_id": report_id,
        "title": title,
        "findings": findings or [],
        "summary": summary,
        "status": status,
        "metadata": metadata or {},
    }

    if generated_at is not None:
        report_kwargs["generated_at"] = generated_at

    return ProductResearchReport(**report_kwargs)


def build_product_research_store(
    *,
    findings: dict[str, ProductResearchFinding] | None = None,
) -> ProductResearchStore:
    """Build product research store."""
    return ProductResearchStore(
        findings=findings or {},
    )


def validate_product_research_findings(
    findings: list[ProductResearchFinding],
) -> list[ProductResearchFinding]:
    """Validate product research findings."""
    if not isinstance(findings, list):
        raise ValueError("Findings must be a list.")

    for finding in findings:
        if not isinstance(finding, ProductResearchFinding):
            raise ValueError("Findings must contain ProductResearchFinding objects.")

    return findings


def summarize_product_research_findings(
    findings: list[ProductResearchFinding],
    *,
    metadata: dict[str, Any] | None = None,
) -> ProductResearchSummary:
    """Summarize product research findings."""
    validate_product_research_findings(findings)

    total = len(findings)
    draft = sum(
        1
        for finding in findings
        if normalize_product_research_status(finding.status) == ProductResearchStatus.DRAFT
    )
    running = sum(
        1
        for finding in findings
        if normalize_product_research_status(finding.status) == ProductResearchStatus.RUNNING
    )
    completed = sum(
        1
        for finding in findings
        if normalize_product_research_status(finding.status) == ProductResearchStatus.COMPLETED
    )
    archived = sum(
        1
        for finding in findings
        if normalize_product_research_status(finding.status) == ProductResearchStatus.ARCHIVED
    )
    high_priority = sum(1 for finding in findings if finding.high_priority)

    average_confidence = (
        round(sum(float(finding.confidence) for finding in findings) / total, 4)
        if total
        else 0.0
    )

    return ProductResearchSummary(
        total=total,
        draft=draft,
        running=running,
        completed=completed,
        archived=archived,
        high_priority=high_priority,
        average_confidence=average_confidence,
        metadata=metadata or {},
    )


def research_finding_to_response(
    *,
    finding: ProductResearchFinding,
    context: ProductApiRequestContext | None = None,
    message: str = "Research finding request completed.",
) -> ProductApiResponse:
    """Convert research finding into product API response."""
    if not isinstance(finding, ProductResearchFinding):
        raise ValueError("Finding must be a ProductResearchFinding.")

    return product_api_success(
        data={
            "finding": finding.to_dict(),
        },
        message=message,
        context=context,
    )


def research_report_to_response(
    *,
    report: ProductResearchReport,
    context: ProductApiRequestContext | None = None,
    message: str = "Research report request completed.",
) -> ProductApiResponse:
    """Convert research report into product API response."""
    if not isinstance(report, ProductResearchReport):
        raise ValueError("Report must be a ProductResearchReport.")

    return product_api_success(
        data={
            "report": report.to_dict(),
        },
        message=message,
        context=context,
    )


def list_research_findings_response(
    *,
    findings: list[ProductResearchFinding],
    query: ProductApiListQuery | None = None,
    context: ProductApiRequestContext | None = None,
    message: str = "Research findings listed successfully.",
) -> ProductApiResponse:
    """Build research finding list response."""
    validate_product_research_findings(findings)

    pagination = query.pagination if query else ProductApiPagination()
    paged_findings = paginate_product_research_findings(
        findings=findings,
        pagination=pagination,
    )
    result = ProductApiListResult(
        items=[finding.to_dict() for finding in paged_findings],
        pagination=pagination,
        total_items=len(findings),
        metadata={
            "summary": summarize_product_research_findings(findings).to_dict(),
        },
    )

    return list_result_to_response(
        result=result,
        context=context,
        message=message,
    )


def create_research_operation_response(
    *,
    finding: ProductResearchFinding,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Build create research operation response."""
    if not isinstance(finding, ProductResearchFinding):
        raise ValueError("Finding must be a ProductResearchFinding.")

    return operation_result_to_response(
        result=ProductApiOperationResult(
            operation=ProductApiOperation.CREATE,
            resource_type=ProductApiRequestType.RESEARCH,
            resource_id=finding.finding_id,
            accepted=True,
            result={
                "finding": finding.to_dict(),
            },
        ),
        context=context,
        message="Research finding created successfully.",
    )


def get_research_finding_response(
    *,
    store: ProductResearchStore,
    finding_id: str,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Get research finding from store and return response."""
    if not isinstance(store, ProductResearchStore):
        raise ValueError("Store must be a ProductResearchStore.")

    finding = store.get(finding_id)

    if finding is None:
        return product_api_failure(
            message="Research finding not found.",
            code=ProductApiErrorCode.NOT_FOUND,
            details={
                "finding_id": finding_id.strip(),
            },
            context=context,
        )

    return research_finding_to_response(
        finding=finding,
        context=context,
        message="Research finding retrieved successfully.",
    )


def update_research_status(
    finding: ProductResearchFinding,
    *,
    status: ProductResearchStatus | str,
    metadata: dict[str, Any] | None = None,
) -> ProductResearchFinding:
    """Update research status by returning a new finding."""
    if not isinstance(finding, ProductResearchFinding):
        raise ValueError("Finding must be a ProductResearchFinding.")

    return build_product_research_finding(
        finding_id=finding.finding_id,
        title=finding.title,
        finding_type=finding.finding_type,
        summary=finding.summary,
        confidence=finding.confidence,
        priority=finding.priority,
        status=status,
        symbol=finding.symbol,
        timeframe=finding.timeframe,
        tags=finding.tags,
        evidence=finding.evidence,
        metadata={
            **finding.metadata,
            **(metadata or {}),
        },
        created_at=finding.created_at,
    )


def archive_research_finding(
    finding: ProductResearchFinding,
    *,
    reason: str = "",
) -> ProductResearchFinding:
    """Archive research finding."""
    validate_string(reason, "Reason")

    return update_research_status(
        finding,
        status=ProductResearchStatus.ARCHIVED,
        metadata={
            "archive_reason": reason.strip(),
        },
    )


def paginate_product_research_findings(
    *,
    findings: list[ProductResearchFinding],
    pagination: ProductApiPagination,
) -> list[ProductResearchFinding]:
    """Paginate product research findings."""
    validate_product_research_findings(findings)

    if not isinstance(pagination, ProductApiPagination):
        raise ValueError("Pagination must be a ProductApiPagination.")

    return findings[pagination.offset : pagination.offset + pagination.page_size]


def filter_product_research_findings(
    *,
    findings: list[ProductResearchFinding],
    symbol: str | None = None,
    timeframe: str | None = None,
    status: ProductResearchStatus | str | None = None,
    priority: ProductResearchPriority | str | None = None,
    finding_type: ProductResearchFindingType | str | None = None,
    tag: str | None = None,
) -> list[ProductResearchFinding]:
    """Filter product research findings."""
    validate_product_research_findings(findings)

    filtered = list(findings)

    if symbol is not None:
        normalized_symbol = validate_product_symbol(symbol)
        filtered = [
            finding
            for finding in filtered
            if finding.symbol and validate_product_symbol(finding.symbol) == normalized_symbol
        ]

    if timeframe is not None:
        normalized_timeframe = validate_product_timeframe(timeframe)
        filtered = [
            finding
            for finding in filtered
            if finding.timeframe and validate_product_timeframe(finding.timeframe) == normalized_timeframe
        ]

    if status is not None:
        normalized_status = normalize_product_research_status(status)
        filtered = [
            finding
            for finding in filtered
            if normalize_product_research_status(finding.status) == normalized_status
        ]

    if priority is not None:
        normalized_priority = normalize_product_research_priority(priority)
        filtered = [
            finding
            for finding in filtered
            if normalize_product_research_priority(finding.priority) == normalized_priority
        ]

    if finding_type is not None:
        normalized_type = normalize_product_research_finding_type(finding_type)
        filtered = [
            finding
            for finding in filtered
            if normalize_product_research_finding_type(finding.finding_type) == normalized_type
        ]

    if tag is not None:
        normalized_tag = validate_non_empty_string(tag, "Tag").lower()
        filtered = [
            finding
            for finding in filtered
            if normalized_tag in {item.strip().lower() for item in finding.tags}
        ]

    return filtered