"""
AQOS production runtime configuration validators.

This module provides dependency-free runtime configuration primitives for
validating required settings, typed values, secrets, and environment profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.production.base import (
    ProductionCheckResult,
    ProductionGateResult,
    ProductionSeverity,
    ProductionStatus,
    aggregate_production_status,
    build_production_check_result,
    build_production_gate_result,
    validate_boolean,
    validate_details,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_string,
)


class ConfigValueType(str, Enum):
    """Supported runtime configuration value types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    SECRET = "secret"


class ConfigRequirementLevel(str, Enum):
    """Supported configuration requirement levels."""

    REQUIRED = "required"
    OPTIONAL = "optional"


@dataclass(frozen=True)
class RuntimeConfigField:
    """Single runtime configuration field definition."""

    name: str
    value_type: ConfigValueType | str
    requirement: ConfigRequirementLevel | str = ConfigRequirementLevel.REQUIRED
    default: Any = None
    secret: bool = False
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_config_key(self.name)
        normalize_config_value_type(self.value_type)
        normalize_config_requirement_level(self.requirement)

        if not isinstance(self.secret, bool):
            raise ValueError("Secret must be a boolean.")

        validate_string(self.description, "Description")
        validate_details(self.metadata)

        if self.default is not None:
            validate_config_value(
                self.default,
                normalize_config_value_type(self.value_type),
                field_name=f"Default for {self.name.strip()}",
            )

    @property
    def required(self) -> bool:
        """Return whether field is required."""
        return normalize_config_requirement_level(self.requirement) == ConfigRequirementLevel.REQUIRED

    def to_dict(self) -> dict[str, Any]:
        """Convert runtime config field into dictionary."""
        return {
            "name": self.name.strip(),
            "value_type": normalize_config_value_type(self.value_type).value,
            "requirement": normalize_config_requirement_level(self.requirement).value,
            "required": self.required,
            "default": mask_secret_value(self.default) if self.secret else self.default,
            "secret": self.secret,
            "description": self.description.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeConfigProfile:
    """Runtime configuration profile."""

    name: str
    environment: str
    fields: list[RuntimeConfigField] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Profile name")
        validate_non_empty_string(self.environment, "Environment")
        validate_runtime_config_fields(self.fields)
        validate_details(self.metadata)

    @property
    def required_keys(self) -> list[str]:
        """Return required field names."""
        return [
            field.name.strip()
            for field in self.fields
            if field.required
        ]

    @property
    def secret_keys(self) -> list[str]:
        """Return secret field names."""
        return [
            field.name.strip()
            for field in self.fields
            if field.secret
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert runtime config profile into dictionary."""
        return {
            "name": self.name.strip(),
            "environment": self.environment.strip(),
            "fields": [
                field.to_dict()
                for field in self.fields
            ],
            "required_keys": self.required_keys,
            "secret_keys": self.secret_keys,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeConfigValidationResult:
    """Runtime configuration validation result."""

    profile: RuntimeConfigProfile
    checks: list[ProductionCheckResult] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, RuntimeConfigProfile):
            raise ValueError("Profile must be a RuntimeConfigProfile.")

        validate_config_checks(self.checks)
        validate_details(self.config)
        validate_details(self.metadata)

    @property
    def status(self) -> ProductionStatus:
        """Return aggregated production status."""
        return aggregate_production_status(self.checks)

    @property
    def passed(self) -> bool:
        """Return whether runtime config passed."""
        return self.status == ProductionStatus.READY

    @property
    def failed(self) -> bool:
        """Return whether runtime config failed."""
        return not self.passed

    @property
    def masked_config(self) -> dict[str, Any]:
        """Return config with secret values masked."""
        secret_keys = set(self.profile.secret_keys)

        return {
            key: mask_secret_value(value) if key in secret_keys else value
            for key, value in self.config.items()
        }

    def to_gate_result(self) -> ProductionGateResult:
        """Convert validation result into production gate result."""
        return build_production_gate_result(
            gate_name="runtime-configuration",
            status=self.status,
            checks=self.checks,
            message="Runtime configuration passed."
            if self.passed
            else "Runtime configuration has issues.",
            metadata={
                "profile": self.profile.to_dict(),
                "config": self.masked_config,
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert validation result into dictionary."""
        return {
            "profile": self.profile.to_dict(),
            "status": self.status.value,
            "passed": self.passed,
            "failed": self.failed,
            "checks": [
                check.to_dict()
                for check in self.checks
            ],
            "config": self.masked_config,
            "metadata": dict(self.metadata),
        }


def normalize_config_value_type(value_type: ConfigValueType | str) -> ConfigValueType:
    """Normalize config value type."""
    if isinstance(value_type, ConfigValueType):
        return value_type

    normalized = validate_non_empty_string(value_type, "Config value type").lower()

    try:
        return ConfigValueType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ConfigValueType)
        raise ValueError(
            f"Invalid config value type '{value_type}'. Valid value types: {valid}.",
        ) from exc


def normalize_config_requirement_level(
    requirement: ConfigRequirementLevel | str,
) -> ConfigRequirementLevel:
    """Normalize config requirement level."""
    if isinstance(requirement, ConfigRequirementLevel):
        return requirement

    normalized = validate_non_empty_string(requirement, "Config requirement level").lower()

    try:
        return ConfigRequirementLevel(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ConfigRequirementLevel)
        raise ValueError(
            f"Invalid config requirement level '{requirement}'. Valid levels: {valid}.",
        ) from exc


def validate_config_key(key: str) -> str:
    """Validate runtime config key."""
    normalized = validate_non_empty_string(key, "Config key")

    if not normalized.replace("_", "").isalnum():
        raise ValueError("Config key must be alphanumeric or underscore.")

    if normalized[0].isdigit():
        raise ValueError("Config key cannot start with a digit.")

    if normalized.upper() != normalized:
        raise ValueError("Config key must be uppercase.")

    return normalized


def validate_config_value(
    value: Any,
    value_type: ConfigValueType | str,
    *,
    field_name: str = "Config value",
) -> Any:
    """Validate runtime config value by type."""
    normalized = normalize_config_value_type(value_type)

    if normalized in {ConfigValueType.STRING, ConfigValueType.SECRET}:
        validate_non_empty_string(value, field_name)
        return value

    if normalized == ConfigValueType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer.")

        return value

    if normalized == ConfigValueType.FLOAT:
        return validate_non_negative_float(value, field_name)

    if normalized == ConfigValueType.BOOLEAN:
        return validate_boolean(value, field_name)

    raise ValueError("Unsupported config value type.")


def mask_secret_value(value: Any) -> str | None:
    """Mask secret value."""
    if value is None:
        return None

    text = str(value)

    if not text:
        return ""

    return "********"


def validate_runtime_config_fields(
    fields: list[RuntimeConfigField],
) -> list[RuntimeConfigField]:
    """Validate runtime config fields."""
    if not isinstance(fields, list):
        raise ValueError("Fields must be a list.")

    seen: set[str] = set()

    for field_item in fields:
        if not isinstance(field_item, RuntimeConfigField):
            raise ValueError("Fields must contain RuntimeConfigField objects.")

        key = field_item.name.strip()

        if key in seen:
            raise ValueError(f"Duplicate config field '{key}'.")

        seen.add(key)

    return fields


def validate_config_checks(
    checks: list[ProductionCheckResult],
) -> list[ProductionCheckResult]:
    """Validate config checks."""
    if not isinstance(checks, list):
        raise ValueError("Checks must be a list.")

    for check in checks:
        if not isinstance(check, ProductionCheckResult):
            raise ValueError("Checks must contain ProductionCheckResult objects.")

    return checks


def build_runtime_config_field(
    *,
    name: str,
    value_type: ConfigValueType | str,
    requirement: ConfigRequirementLevel | str = ConfigRequirementLevel.REQUIRED,
    default: Any = None,
    secret: bool = False,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> RuntimeConfigField:
    """Build runtime config field."""
    return RuntimeConfigField(
        name=name,
        value_type=value_type,
        requirement=requirement,
        default=default,
        secret=secret,
        description=description,
        metadata=metadata or {},
    )


def build_runtime_config_profile(
    *,
    name: str,
    environment: str,
    fields: list[RuntimeConfigField] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeConfigProfile:
    """Build runtime config profile."""
    return RuntimeConfigProfile(
        name=name,
        environment=environment,
        fields=fields or [],
        metadata=metadata or {},
    )


def build_runtime_config_validation_result(
    *,
    profile: RuntimeConfigProfile,
    checks: list[ProductionCheckResult] | None = None,
    config: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeConfigValidationResult:
    """Build runtime config validation result."""
    return RuntimeConfigValidationResult(
        profile=profile,
        checks=checks or [],
        config=config or {},
        metadata=metadata or {},
    )


def resolve_runtime_config(
    *,
    profile: RuntimeConfigProfile,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Resolve runtime config values with defaults."""
    if not isinstance(profile, RuntimeConfigProfile):
        raise ValueError("Profile must be a RuntimeConfigProfile.")

    validate_details(values)

    resolved: dict[str, Any] = {}

    for field_item in profile.fields:
        key = field_item.name.strip()

        if key in values:
            resolved[key] = values[key]
        elif field_item.default is not None:
            resolved[key] = field_item.default

    return resolved


def validate_runtime_config(
    *,
    profile: RuntimeConfigProfile,
    values: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> RuntimeConfigValidationResult:
    """Validate runtime config against profile."""
    if not isinstance(profile, RuntimeConfigProfile):
        raise ValueError("Profile must be a RuntimeConfigProfile.")

    validate_details(values)

    if metadata is not None:
        validate_details(metadata)

    resolved = resolve_runtime_config(
        profile=profile,
        values=values,
    )
    checks: list[ProductionCheckResult] = []

    for field_item in profile.fields:
        key = field_item.name.strip()
        value = resolved.get(key)

        if value is None or value == "":
            if field_item.required:
                checks.append(
                    build_production_check_result(
                        name=f"config-{key}",
                        status=ProductionStatus.BLOCKED,
                        severity=ProductionSeverity.CRITICAL,
                        passed=False,
                        message="Required configuration value is missing.",
                        details={
                            "key": key,
                            "value_type": normalize_config_value_type(field_item.value_type).value,
                            "required": field_item.required,
                        },
                    ),
                )
            else:
                checks.append(
                    build_production_check_result(
                        name=f"config-{key}",
                        status=ProductionStatus.WARNING,
                        severity=ProductionSeverity.WARNING,
                        passed=True,
                        message="Optional configuration value is missing.",
                        details={
                            "key": key,
                            "value_type": normalize_config_value_type(field_item.value_type).value,
                            "required": field_item.required,
                        },
                    ),
                )
            continue

        try:
            validate_config_value(
                value,
                field_item.value_type,
                field_name=key,
            )
        except ValueError as exc:
            checks.append(
                build_production_check_result(
                    name=f"config-{key}",
                    status=ProductionStatus.BLOCKED,
                    severity=ProductionSeverity.ERROR,
                    passed=False,
                    message="Configuration value has invalid type.",
                    details={
                        "key": key,
                        "value_type": normalize_config_value_type(field_item.value_type).value,
                        "error": str(exc),
                    },
                ),
            )
            continue

        checks.append(
            build_production_check_result(
                name=f"config-{key}",
                status=ProductionStatus.READY,
                severity=ProductionSeverity.INFO,
                passed=True,
                message="Configuration value is valid.",
                details={
                    "key": key,
                    "value_type": normalize_config_value_type(field_item.value_type).value,
                    "secret": field_item.secret,
                },
            ),
        )

    return build_runtime_config_validation_result(
        profile=profile,
        checks=checks,
        config=resolved,
        metadata=metadata or {},
    )


def runtime_config_to_gate_result(
    *,
    profile: RuntimeConfigProfile,
    values: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> ProductionGateResult:
    """Validate runtime config and return gate result."""
    return validate_runtime_config(
        profile=profile,
        values=values,
        metadata=metadata,
    ).to_gate_result()


def build_default_runtime_config_profile(
    *,
    environment: str = "production",
) -> RuntimeConfigProfile:
    """Build default AQOS runtime configuration profile."""
    return build_runtime_config_profile(
        name="aqos-runtime",
        environment=environment,
        fields=[
            build_runtime_config_field(
                name="AQOS_ENV",
                value_type=ConfigValueType.STRING,
                requirement=ConfigRequirementLevel.REQUIRED,
                default=environment,
                description="AQOS runtime environment.",
            ),
            build_runtime_config_field(
                name="DATABASE_URL",
                value_type=ConfigValueType.SECRET,
                requirement=ConfigRequirementLevel.REQUIRED,
                secret=True,
                description="Primary database connection string.",
            ),
            build_runtime_config_field(
                name="LOG_LEVEL",
                value_type=ConfigValueType.STRING,
                requirement=ConfigRequirementLevel.OPTIONAL,
                default="INFO",
                description="Runtime log level.",
            ),
            build_runtime_config_field(
                name="ENABLE_TRADING",
                value_type=ConfigValueType.BOOLEAN,
                requirement=ConfigRequirementLevel.REQUIRED,
                default=False,
                description="Whether live trading execution is enabled.",
            ),
            build_runtime_config_field(
                name="MAX_WORKERS",
                value_type=ConfigValueType.INTEGER,
                requirement=ConfigRequirementLevel.OPTIONAL,
                default=4,
                description="Maximum worker count.",
            ),
        ],
        metadata={
            "generated_by": "aqos.production",
        },
    )