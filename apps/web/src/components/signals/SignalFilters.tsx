"use client";

import type { SignalListQuery } from "@/api/resources";
import { Button, Field, Input, Select } from "@/components/ui";

/**
 * The filters a caller may apply to their own signals.
 *
 * There is no `user_id` control. The backend already scopes every list to the
 * caller, so the field could only ever be used to ask for somebody else's
 * data — which is refused. Offering it would teach callers to try.
 */

export const SIGNAL_STATUSES = [
  "generated",
  "pending_approval",
  "approved",
  "rejected",
  "missed",
  "expired",
  "executed",
  "failed",
  "cancelled",
] as const;

export const SIGNAL_ACTIONS = ["buy", "sell", "close", "hold"] as const;

export const SIGNAL_SOURCES = ["ml_model", "rule_based", "manual", "hybrid"] as const;

export interface SignalFilterValues {
  readonly symbol: string;
  readonly status: string;
  readonly action: string;
  readonly source: string;
  readonly generated_from: string;
  readonly generated_to: string;
}

export const EMPTY_FILTERS: SignalFilterValues = {
  symbol: "",
  status: "",
  action: "",
  source: "",
  generated_from: "",
  generated_to: "",
};

/**
 * Turn the form into a query, dropping anything blank.
 *
 * A blank field means "no opinion", not "match the empty string", so it must
 * not reach the API as a filter that would match nothing.
 */
export function buildSignalQuery(
  values: SignalFilterValues,
  limit: number,
  offset: number,
): SignalListQuery {
  const query: Record<string, string | number> = { limit, offset };

  for (const [key, value] of Object.entries(values)) {
    const trimmed = value.trim();

    if (trimmed) {
      query[key] = trimmed;
    }
  }

  return query as SignalListQuery;
}

export function SignalFilters({
  values,
  onChange,
  onApply,
  onReset,
  disabled,
}: {
  readonly values: SignalFilterValues;
  readonly onChange: (values: SignalFilterValues) => void;
  readonly onApply: () => void;
  readonly onReset: () => void;
  readonly disabled?: boolean;
}) {
  const set = (key: keyof SignalFilterValues) => (value: string) =>
    onChange({ ...values, [key]: value });

  return (
    <form
      aria-label="Signal filters"
      className="mb-6 grid gap-3 sm:grid-cols-3"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <Field label="Symbol" htmlFor="filter-symbol">
        <Input
          id="filter-symbol"
          value={values.symbol}
          onChange={(event) => set("symbol")(event.target.value)}
        />
      </Field>
      <Field label="Status" htmlFor="filter-status">
        <Select
          id="filter-status"
          value={values.status}
          onChange={(event) => set("status")(event.target.value)}
        >
          <option value="">Any</option>
          {SIGNAL_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Action" htmlFor="filter-action">
        <Select
          id="filter-action"
          value={values.action}
          onChange={(event) => set("action")(event.target.value)}
        >
          <option value="">Any</option>
          {SIGNAL_ACTIONS.map((action) => (
            <option key={action} value={action}>
              {action}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Source" htmlFor="filter-source">
        <Select
          id="filter-source"
          value={values.source}
          onChange={(event) => set("source")(event.target.value)}
        >
          <option value="">Any</option>
          {SIGNAL_SOURCES.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Generated from" htmlFor="filter-from" hint="ISO timestamp">
        <Input
          id="filter-from"
          value={values.generated_from}
          onChange={(event) => set("generated_from")(event.target.value)}
        />
      </Field>
      <Field label="Generated to" htmlFor="filter-to" hint="ISO timestamp">
        <Input
          id="filter-to"
          value={values.generated_to}
          onChange={(event) => set("generated_to")(event.target.value)}
        />
      </Field>
      <div className="flex items-end gap-2 sm:col-span-3">
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
