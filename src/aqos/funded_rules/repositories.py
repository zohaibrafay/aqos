from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.funded_rules.evaluation import (
    FundedAccountState,
    FundedRuleEvaluation,
    FundedTradeRequest,
    evaluate_funded_rules,
)
from aqos.funded_rules.models import (
    FundedAccountRules,
    FundedRuleStatus,
    FundedRuleTemplate,
    normalize_rule_name,
)
from aqos.users.repositories import build_entity_id


AQOS_FUNDED_RULE_REPOSITORIES_VERSION = "1.0"


class FundedRuleTemplateRepository(AqosRepository[FundedRuleTemplate]):
    """Named, reusable funded rule configurations."""

    model = FundedRuleTemplate

    def create_template(
        self,
        name: str,
        description: str | None = None,
        is_active: bool = True,
        metadata: dict[str, Any] | None = None,
        template_id: str | None = None,
        created_at_utc: datetime | None = None,
        **rule_values: Any,
    ) -> FundedRuleTemplate:
        normalized_name = normalize_rule_name(name)

        if self.find_by_name(normalized_name) is not None:
            raise RepositoryError(
                f"Funded rule template name already exists: {normalized_name}"
            )

        timestamp = created_at_utc or database_utc_now()

        template = FundedRuleTemplate(
            template_id=template_id or build_entity_id("fundedtpl"),
            name=normalized_name,
            description=description,
            is_active=is_active,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
            **rule_values,
        )
        template.validate_consistency()

        self.add(template)
        self.flush()

        return template

    def find_by_name(self, name: str) -> FundedRuleTemplate | None:
        return self.session.execute(
            select(FundedRuleTemplate).where(
                FundedRuleTemplate.name == (name or "").strip()
            )
        ).scalar_one_or_none()

    def require_template(self, template_id: str) -> FundedRuleTemplate:
        return self.require(template_id)

    def list_templates(
        self,
        active_only: bool = False,
    ) -> tuple[FundedRuleTemplate, ...]:
        statement = select(FundedRuleTemplate)

        if active_only:
            statement = statement.where(FundedRuleTemplate.is_active.is_(True))

        statement = statement.order_by(FundedRuleTemplate.name)

        return tuple(self.session.execute(statement).scalars().all())

    def update_template(
        self,
        template_id: str,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: datetime | None = None,
        **rule_values: Any,
    ) -> FundedRuleTemplate:
        template = self.require_template(template_id)

        if name is not None:
            normalized_name = normalize_rule_name(name)
            existing = self.find_by_name(normalized_name)

            if existing is not None and existing.template_id != template_id:
                raise RepositoryError(
                    f"Funded rule template name already exists: {normalized_name}"
                )

            template.name = normalized_name

        if description is not None:
            template.description = description

        if is_active is not None:
            template.is_active = is_active

        if metadata is not None:
            template.extra_metadata = metadata

        for field_name, value in rule_values.items():
            if value is None:
                continue

            if not hasattr(template, field_name):
                raise RepositoryError(
                    f"Funded rule template has no field named {field_name}."
                )

            setattr(template, field_name, value)

        template.updated_at_utc = updated_at_utc or database_utc_now()
        template.validate_consistency()

        self.flush()

        return template

    def delete_template(self, template_id: str) -> bool:
        return self.delete_by_primary_key(template_id)


class FundedAccountRulesRepository(AqosRepository[FundedAccountRules]):
    """
    Funded rules applied to one trading account.

    Template values are copied at assignment time, so editing a template never
    silently changes what an account is already trading under.
    """

    model = FundedAccountRules

    def assign_rules(
        self,
        account_id: str,
        template: FundedRuleTemplate | None = None,
        status: FundedRuleStatus = FundedRuleStatus.ACTIVE,
        metadata: dict[str, Any] | None = None,
        rules_id: str | None = None,
        created_at_utc: datetime | None = None,
        **overrides: Any,
    ) -> FundedAccountRules:
        if self.get_for_account(account_id) is not None:
            raise RepositoryError(
                f"Funded rules already exist for account: {account_id}"
            )

        timestamp = created_at_utc or database_utc_now()

        values: dict[str, Any] = {}

        if template is not None:
            if not template.is_active:
                raise RepositoryError(
                    f"Funded rule template is not active: {template.name}"
                )

            values.update(template.rule_values())

        values.update(
            {key: value for key, value in overrides.items() if value is not None}
        )

        rules = FundedAccountRules(
            rules_id=rules_id or build_entity_id("fundedrules"),
            account_id=account_id,
            template_id=template.template_id if template is not None else None,
            status=status,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
            **values,
        )
        rules.validate_consistency()
        rules.validate_breach_record()

        self.add(rules)
        self.flush()

        return rules

    def get_for_account(self, account_id: str) -> FundedAccountRules | None:
        return self.session.execute(
            select(FundedAccountRules).where(
                FundedAccountRules.account_id == account_id
            )
        ).scalar_one_or_none()

    def require_for_account(self, account_id: str) -> FundedAccountRules:
        rules = self.get_for_account(account_id)

        if rules is None:
            raise RepositoryError(
                f"Funded rules do not exist for account: {account_id}"
            )

        return rules

    def list_rules(
        self,
        status: FundedRuleStatus | None = None,
        template_id: str | None = None,
    ) -> tuple[FundedAccountRules, ...]:
        statement = select(FundedAccountRules)

        if status is not None:
            statement = statement.where(FundedAccountRules.status == status)

        if template_id is not None:
            statement = statement.where(
                FundedAccountRules.template_id == template_id
            )

        statement = statement.order_by(
            FundedAccountRules.created_at_utc,
            FundedAccountRules.rules_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def update_rules(
        self,
        account_id: str,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: datetime | None = None,
        **rule_values: Any,
    ) -> FundedAccountRules:
        rules = self.require_for_account(account_id)

        for field_name, value in rule_values.items():
            if value is None:
                continue

            if not hasattr(rules, field_name):
                raise RepositoryError(
                    f"Funded account rules have no field named {field_name}."
                )

            setattr(rules, field_name, value)

        if metadata is not None:
            rules.extra_metadata = metadata

        rules.updated_at_utc = updated_at_utc or database_utc_now()
        rules.validate_consistency()
        rules.validate_breach_record()

        self.flush()

        return rules

    def set_status(
        self,
        account_id: str,
        status: FundedRuleStatus,
        breach_reason: str | None = None,
        breached_at_utc: datetime | None = None,
        updated_at_utc: datetime | None = None,
    ) -> FundedAccountRules:
        rules = self.require_for_account(account_id)

        timestamp = updated_at_utc or database_utc_now()

        rules.status = status

        if status == FundedRuleStatus.BREACHED:
            rules.breached_at_utc = breached_at_utc or timestamp
            rules.breach_reason = breach_reason
        elif status == FundedRuleStatus.ACTIVE:
            rules.breached_at_utc = None
            rules.breach_reason = None

        rules.updated_at_utc = timestamp
        rules.validate_breach_record()

        self.flush()

        return rules

    def mark_breached(
        self,
        account_id: str,
        reason: str,
        breached_at_utc: datetime | None = None,
    ) -> FundedAccountRules:
        if not (reason or "").strip():
            raise RepositoryError("A breach reason is required.")

        return self.set_status(
            account_id=account_id,
            status=FundedRuleStatus.BREACHED,
            breach_reason=reason,
            breached_at_utc=breached_at_utc,
        )

    def evaluate_and_record(
        self,
        account_id: str,
        state: FundedAccountState,
        request: FundedTradeRequest | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> FundedRuleEvaluation:
        """
        Evaluate the rules and persist a breach when one is found.

        Recording the breach is what makes the funded ceiling drop to DISABLED
        on every later resolution, rather than only for this one decision.
        """

        rules = self.require_for_account(account_id)
        evaluation = evaluate_funded_rules(rules, state, request)

        if not evaluation.passed and rules.status == FundedRuleStatus.ACTIVE:
            self.mark_breached(
                account_id=account_id,
                reason=evaluation.breach_summary(),
                breached_at_utc=occurred_at_utc,
            )

        return evaluation

    def delete_for_account(self, account_id: str) -> bool:
        rules = self.get_for_account(account_id)

        if rules is None:
            return False

        self.session.delete(rules)
        self.flush()

        return True


__all__ = [
    "AQOS_FUNDED_RULE_REPOSITORIES_VERSION",
    "FundedAccountRulesRepository",
    "FundedRuleTemplateRepository",
]
