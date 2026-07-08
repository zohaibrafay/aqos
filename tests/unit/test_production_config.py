"""
Unit tests for AQOS production runtime configuration validators.
"""

import pytest

from aqos.production import (
    ConfigRequirementLevel,
    ConfigValueType,
    ProductionStatus,
    RuntimeConfigField,
    RuntimeConfigProfile,
    RuntimeConfigValidationResult,
    build_default_runtime_config_profile,
    build_runtime_config_field,
    build_runtime_config_profile,
    build_runtime_config_validation_result,
    mask_secret_value,
    normalize_config_requirement_level,
    normalize_config_value_type,
    resolve_runtime_config,
    runtime_config_to_gate_result,
    validate_config_checks,
    validate_config_key,
    validate_config_value,
    validate_runtime_config,
    validate_runtime_config_fields,
)


def test_config_value_type_values():
    assert ConfigValueType.STRING.value == "string"
    assert ConfigValueType.INTEGER.value == "integer"
    assert ConfigValueType.FLOAT.value == "float"
    assert ConfigValueType.BOOLEAN.value == "boolean"
    assert ConfigValueType.SECRET.value == "secret"


def test_config_requirement_level_values():
    assert ConfigRequirementLevel.REQUIRED.value == "required"
    assert ConfigRequirementLevel.OPTIONAL.value == "optional"


def test_normalize_config_value_type_accepts_enum_and_string():
    assert normalize_config_value_type(ConfigValueType.STRING) == ConfigValueType.STRING
    assert normalize_config_value_type(" STRING ") == ConfigValueType.STRING
    assert normalize_config_value_type("integer") == ConfigValueType.INTEGER
    assert normalize_config_value_type("BOOLEAN") == ConfigValueType.BOOLEAN


def test_normalize_config_value_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_config_value_type("bad")

    with pytest.raises(ValueError):
        normalize_config_value_type("")


def test_normalize_config_requirement_level_accepts_enum_and_string():
    assert normalize_config_requirement_level(ConfigRequirementLevel.REQUIRED) == ConfigRequirementLevel.REQUIRED
    assert normalize_config_requirement_level(" REQUIRED ") == ConfigRequirementLevel.REQUIRED
    assert normalize_config_requirement_level("optional") == ConfigRequirementLevel.OPTIONAL


def test_normalize_config_requirement_level_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_config_requirement_level("bad")

    with pytest.raises(ValueError):
        normalize_config_requirement_level("")


def test_validate_config_key():
    assert validate_config_key("DATABASE_URL") == "DATABASE_URL"
    assert validate_config_key("AQOS_ENV") == "AQOS_ENV"

    with pytest.raises(ValueError):
        validate_config_key("")

    with pytest.raises(ValueError):
        validate_config_key("database_url")

    with pytest.raises(ValueError):
        validate_config_key("1_DATABASE")

    with pytest.raises(ValueError):
        validate_config_key("BAD-NAME")


def test_validate_config_value():
    assert validate_config_value("value", "string") == "value"
    assert validate_config_value("secret", "secret") == "secret"
    assert validate_config_value(1, "integer") == 1
    assert validate_config_value(1.5, "float") == 1.5
    assert validate_config_value(True, "boolean") is True

    with pytest.raises(ValueError):
        validate_config_value("", "string")

    with pytest.raises(ValueError):
        validate_config_value(True, "integer")

    with pytest.raises(ValueError):
        validate_config_value("1", "integer")

    with pytest.raises(ValueError):
        validate_config_value(-1, "float")

    with pytest.raises(ValueError):
        validate_config_value("true", "boolean")


def test_mask_secret_value():
    assert mask_secret_value(None) is None
    assert mask_secret_value("") == ""
    assert mask_secret_value("abc") == "********"
    assert mask_secret_value(123) == "********"


def test_runtime_config_field_to_dict():
    field = RuntimeConfigField(
        name=" DATABASE_URL ",
        value_type="SECRET",
        requirement="REQUIRED",
        default="postgres://example",
        secret=True,
        description=" Database URL. ",
        metadata={
            "scope": "db",
        },
    )

    assert field.required is True

    assert field.to_dict() == {
        "name": "DATABASE_URL",
        "value_type": "secret",
        "requirement": "required",
        "required": True,
        "default": "********",
        "secret": True,
        "description": "Database URL.",
        "metadata": {
            "scope": "db",
        },
    }


def test_runtime_config_field_rejects_invalid_values():
    with pytest.raises(ValueError):
        RuntimeConfigField(name="", value_type="string")

    with pytest.raises(ValueError):
        RuntimeConfigField(name="bad", value_type="string")

    with pytest.raises(ValueError):
        RuntimeConfigField(name="DATABASE_URL", value_type="bad")

    with pytest.raises(ValueError):
        RuntimeConfigField(name="DATABASE_URL", value_type="string", requirement="bad")

    with pytest.raises(ValueError):
        RuntimeConfigField(name="DATABASE_URL", value_type="string", secret="yes")

    with pytest.raises(ValueError):
        RuntimeConfigField(name="DATABASE_URL", value_type="string", description=123)

    with pytest.raises(ValueError):
        RuntimeConfigField(name="DATABASE_URL", value_type="string", metadata=[])

    with pytest.raises(ValueError):
        RuntimeConfigField(name="MAX_WORKERS", value_type="integer", default="4")


def test_build_runtime_config_field():
    field = build_runtime_config_field(
        name="LOG_LEVEL",
        value_type="string",
        requirement="optional",
        default="INFO",
    )

    assert isinstance(field, RuntimeConfigField)
    assert field.required is False
    assert field.default == "INFO"


def test_runtime_config_profile_to_dict():
    field = build_runtime_config_field(
        name="DATABASE_URL",
        value_type="secret",
        secret=True,
    )
    profile = RuntimeConfigProfile(
        name=" aqos-runtime ",
        environment=" production ",
        fields=[field],
        metadata={
            "version": "v1",
        },
    )

    payload = profile.to_dict()

    assert payload["name"] == "aqos-runtime"
    assert payload["environment"] == "production"
    assert payload["required_keys"] == ["DATABASE_URL"]
    assert payload["secret_keys"] == ["DATABASE_URL"]


def test_runtime_config_profile_rejects_invalid_values():
    field = build_runtime_config_field(
        name="DATABASE_URL",
        value_type="secret",
    )

    with pytest.raises(ValueError):
        RuntimeConfigProfile(name="", environment="production")

    with pytest.raises(ValueError):
        RuntimeConfigProfile(name="profile", environment="")

    with pytest.raises(ValueError):
        RuntimeConfigProfile(name="profile", environment="production", fields=["bad"])

    with pytest.raises(ValueError):
        RuntimeConfigProfile(name="profile", environment="production", fields=[field, field])

    with pytest.raises(ValueError):
        RuntimeConfigProfile(name="profile", environment="production", metadata=[])


def test_validate_runtime_config_fields():
    field = build_runtime_config_field(
        name="DATABASE_URL",
        value_type="secret",
    )

    assert validate_runtime_config_fields([field]) == [field]

    with pytest.raises(ValueError):
        validate_runtime_config_fields("bad")

    with pytest.raises(ValueError):
        validate_runtime_config_fields(["bad"])

    with pytest.raises(ValueError):
        validate_runtime_config_fields([field, field])


def test_build_runtime_config_profile():
    profile = build_runtime_config_profile(
        name="profile",
        environment="production",
        fields=[
            build_runtime_config_field(
                name="AQOS_ENV",
                value_type="string",
            ),
        ],
        metadata={
            "source": "test",
        },
    )

    assert isinstance(profile, RuntimeConfigProfile)
    assert profile.metadata == {
        "source": "test",
    }


def test_resolve_runtime_config_uses_defaults():
    profile = build_runtime_config_profile(
        name="profile",
        environment="production",
        fields=[
            build_runtime_config_field(
                name="AQOS_ENV",
                value_type="string",
                default="production",
            ),
            build_runtime_config_field(
                name="DATABASE_URL",
                value_type="secret",
            ),
        ],
    )

    resolved = resolve_runtime_config(
        profile=profile,
        values={
            "DATABASE_URL": "postgres://example",
        },
    )

    assert resolved == {
        "AQOS_ENV": "production",
        "DATABASE_URL": "postgres://example",
    }


def test_resolve_runtime_config_rejects_invalid_values():
    profile = build_default_runtime_config_profile()

    with pytest.raises(ValueError):
        resolve_runtime_config(
            profile="bad",
            values={},
        )

    with pytest.raises(ValueError):
        resolve_runtime_config(
            profile=profile,
            values=[],
        )


def test_validate_runtime_config_success():
    profile = build_default_runtime_config_profile()

    result = validate_runtime_config(
        profile=profile,
        values={
            "DATABASE_URL": "postgres://example",
        },
        metadata={
            "source": "test",
        },
    )

    assert isinstance(result, RuntimeConfigValidationResult)
    assert result.passed is True
    assert result.status == ProductionStatus.READY
    assert result.metadata == {
        "source": "test",
    }
    assert result.masked_config["DATABASE_URL"] == "********"
    assert result.masked_config["AQOS_ENV"] == "production"


def test_validate_runtime_config_missing_required_blocks():
    profile = build_default_runtime_config_profile()

    result = validate_runtime_config(
        profile=profile,
        values={},
    )

    assert result.failed is True
    assert result.status == ProductionStatus.BLOCKED
    assert any(check.status == ProductionStatus.BLOCKED for check in result.checks)


def test_validate_runtime_config_optional_missing_warns():
    profile = build_runtime_config_profile(
        name="profile",
        environment="production",
        fields=[
            build_runtime_config_field(
                name="OPTIONAL_VALUE",
                value_type="string",
                requirement="optional",
            ),
        ],
    )

    result = validate_runtime_config(
        profile=profile,
        values={},
    )

    assert result.status == ProductionStatus.WARNING
    assert result.checks[0].passed is True
    assert result.checks[0].message == "Optional configuration value is missing."


def test_validate_runtime_config_invalid_type_blocks():
    profile = build_runtime_config_profile(
        name="profile",
        environment="production",
        fields=[
            build_runtime_config_field(
                name="MAX_WORKERS",
                value_type="integer",
            ),
        ],
    )

    result = validate_runtime_config(
        profile=profile,
        values={
            "MAX_WORKERS": "4",
        },
    )

    assert result.status == ProductionStatus.BLOCKED
    assert result.checks[0].message == "Configuration value has invalid type."


def test_validate_runtime_config_rejects_invalid_values():
    profile = build_default_runtime_config_profile()

    with pytest.raises(ValueError):
        validate_runtime_config(
            profile="bad",
            values={},
        )

    with pytest.raises(ValueError):
        validate_runtime_config(
            profile=profile,
            values=[],
        )

    with pytest.raises(ValueError):
        validate_runtime_config(
            profile=profile,
            values={},
            metadata=[],
        )


def test_runtime_config_validation_result_to_dict_and_gate_result():
    profile = build_default_runtime_config_profile()
    result = validate_runtime_config(
        profile=profile,
        values={
            "DATABASE_URL": "postgres://example",
        },
    )

    payload = result.to_dict()

    assert payload["status"] == "ready"
    assert payload["passed"] is True
    assert payload["config"]["DATABASE_URL"] == "********"

    gate = result.to_gate_result()

    assert gate.gate_name == "runtime-configuration"
    assert gate.status == ProductionStatus.READY
    assert gate.passed is True


def test_runtime_config_validation_result_rejects_invalid_values():
    profile = build_default_runtime_config_profile()

    with pytest.raises(ValueError):
        RuntimeConfigValidationResult(profile="bad")

    with pytest.raises(ValueError):
        RuntimeConfigValidationResult(profile=profile, checks=["bad"])

    with pytest.raises(ValueError):
        RuntimeConfigValidationResult(profile=profile, config=[])

    with pytest.raises(ValueError):
        RuntimeConfigValidationResult(profile=profile, metadata=[])


def test_build_runtime_config_validation_result():
    profile = build_default_runtime_config_profile()
    result = build_runtime_config_validation_result(
        profile=profile,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(result, RuntimeConfigValidationResult)
    assert result.metadata == {
        "source": "test",
    }


def test_validate_config_checks():
    profile = build_default_runtime_config_profile()
    result = validate_runtime_config(
        profile=profile,
        values={
            "DATABASE_URL": "postgres://example",
        },
    )

    assert validate_config_checks(result.checks) == result.checks

    with pytest.raises(ValueError):
        validate_config_checks("bad")

    with pytest.raises(ValueError):
        validate_config_checks(["bad"])


def test_runtime_config_to_gate_result():
    profile = build_default_runtime_config_profile()

    gate = runtime_config_to_gate_result(
        profile=profile,
        values={
            "DATABASE_URL": "postgres://example",
        },
        metadata={
            "source": "test",
        },
    )

    assert gate.gate_name == "runtime-configuration"
    assert gate.status == ProductionStatus.READY
    assert gate.metadata["source"] == "test"


def test_build_default_runtime_config_profile():
    profile = build_default_runtime_config_profile(
        environment="production",
    )

    assert isinstance(profile, RuntimeConfigProfile)
    assert profile.name == "aqos-runtime"
    assert profile.environment == "production"
    assert "AQOS_ENV" in profile.required_keys
    assert "DATABASE_URL" in profile.required_keys
    assert "DATABASE_URL" in profile.secret_keys


def test_production_config_exports_exist():
    import aqos.production as production

    expected_exports = [
        "ConfigRequirementLevel",
        "ConfigValueType",
        "RuntimeConfigField",
        "RuntimeConfigProfile",
        "RuntimeConfigValidationResult",
        "build_default_runtime_config_profile",
        "build_runtime_config_field",
        "build_runtime_config_profile",
        "build_runtime_config_validation_result",
        "mask_secret_value",
        "normalize_config_requirement_level",
        "normalize_config_value_type",
        "resolve_runtime_config",
        "runtime_config_to_gate_result",
        "validate_config_checks",
        "validate_config_key",
        "validate_config_value",
        "validate_runtime_config",
        "validate_runtime_config_fields",
    ]

    for export_name in expected_exports:
        assert hasattr(production, export_name), export_name