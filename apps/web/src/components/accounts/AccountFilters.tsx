"use client";

import type { AccountListQuery } from "@/api/resources";
import { Button, Field, Select } from "@/components/ui";

/**
 * Filters for a caller's own accounts.
 *
 * No `user_id` control, for the same reason the signal filters have none: the
 * backend scopes every list to the caller, so the field could only be used to
 * ask for somebody else's data.
 */

export const ACCOUNT_TYPES = ["paper", "live", "funded", "demo"] as const;

export const ACCOUNT_STATUSES = ["active", "suspended", "disabled", "closed"] as const;

export const EXECUTION_MODES = [
  "signal_only",
  "manual_approval",
  "auto_trade",
  "disabled",
] as const;

export const VENUES = ["internal_paper", "mt5", "binance", "manual"] as const;

export interface AccountFilterValues {
  readonly account_type: string;
  readonly venue: string;
  readonly status: string;
  readonly execution_mode: string;
}

export const EMPTY_ACCOUNT_FILTERS: AccountFilterValues = {
  account_type: "",
  venue: "",
  status: "",
  execution_mode: "",
};

/** Turn the form into a query, dropping anything the caller left alone. */
export function buildAccountQuery(
  values: AccountFilterValues,
  limit: number,
  offset: number,
): AccountListQuery {
  const query: Record<string, string | number> = { limit, offset };

  for (const [key, value] of Object.entries(values)) {
    const trimmed = value.trim();

    if (trimmed) {
      query[key] = trimmed;
    }
  }

  return query as AccountListQuery;
}

function FilterSelect({
  id,
  label,
  value,
  options,
  onChange,
}: {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly options: readonly string[];
  readonly onChange: (value: string) => void;
}) {
  return (
    <Field label={label} htmlFor={id}>
      <Select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function AccountFilters({
  values,
  onChange,
  onApply,
  onReset,
  disabled,
}: {
  readonly values: AccountFilterValues;
  readonly onChange: (values: AccountFilterValues) => void;
  readonly onApply: () => void;
  readonly onReset: () => void;
  readonly disabled?: boolean;
}) {
  const set = (key: keyof AccountFilterValues) => (value: string) =>
    onChange({ ...values, [key]: value });

  return (
    <form
      aria-label="Account filters"
      className="mb-6 grid gap-3 sm:grid-cols-4"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <FilterSelect
        id="filter-account-type"
        label="Type"
        value={values.account_type}
        options={ACCOUNT_TYPES}
        onChange={set("account_type")}
      />
      <FilterSelect
        id="filter-venue"
        label="Venue"
        value={values.venue}
        options={VENUES}
        onChange={set("venue")}
      />
      <FilterSelect
        id="filter-account-status"
        label="Status"
        value={values.status}
        options={ACCOUNT_STATUSES}
        onChange={set("status")}
      />
      <FilterSelect
        id="filter-execution-mode"
        label="Execution mode"
        value={values.execution_mode}
        options={EXECUTION_MODES}
        onChange={set("execution_mode")}
      />
      <div className="flex items-end gap-2 sm:col-span-4">
        <Button type="submit" disabled={disabled}>
          Apply filters
        </Button>
        <Button type="button" variant="secondary" onClick={onReset} disabled={disabled}>
          Reset
        </Button>
      </div>
    </form>
  );
}
