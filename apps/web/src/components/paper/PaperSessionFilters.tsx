"use client";

import type { PaperSessionListQuery } from "@/api/resources";
import { Button, Field, Input, Select } from "@/components/ui";

/**
 * Filters for a caller's own paper sessions.
 *
 * No `user_id` control: the backend scopes every list to the caller, so the
 * field could only be used to ask for somebody else's runs.
 */

export const SESSION_STATUSES = [
  "created",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
] as const;

export const SESSION_TYPES = [
  "manual_paper_session",
  "model_forward_test",
  "strategy_forward_test",
] as const;

export interface PaperFilterValues {
  readonly account_id: string;
  readonly session_type: string;
  readonly status: string;
  readonly symbol: string;
  readonly strategy_name: string;
  readonly model_id: string;
  readonly started_from: string;
  readonly started_to: string;
}

export const EMPTY_PAPER_FILTERS: PaperFilterValues = {
  account_id: "",
  session_type: "",
  status: "",
  symbol: "",
  strategy_name: "",
  model_id: "",
  started_from: "",
  started_to: "",
};

/** Turn the form into a query, dropping anything the caller left alone. */
export function buildPaperQuery(
  values: PaperFilterValues,
  limit: number,
  offset: number,
): PaperSessionListQuery {
  const query: Record<string, string | number> = { limit, offset };

  for (const [key, value] of Object.entries(values)) {
    const trimmed = value.trim();

    if (trimmed) {
      query[key] = trimmed;
    }
  }

  return query as PaperSessionListQuery;
}

export function PaperSessionFilters({
  values,
  onChange,
  onApply,
  onReset,
  disabled,
}: {
  readonly values: PaperFilterValues;
  readonly onChange: (values: PaperFilterValues) => void;
  readonly onApply: () => void;
  readonly onReset: () => void;
  readonly disabled?: boolean;
}) {
  const set = (key: keyof PaperFilterValues) => (value: string) =>
    onChange({ ...values, [key]: value });

  return (
    <form
      aria-label="Paper session filters"
      className="mb-6 grid gap-3 sm:grid-cols-4"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <Field label="Status" htmlFor="paper-status">
        <Select
          id="paper-status"
          value={values.status}
          onChange={(event) => set("status")(event.target.value)}
        >
          <option value="">Any</option>
          {SESSION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Type" htmlFor="paper-type">
        <Select
          id="paper-type"
          value={values.session_type}
          onChange={(event) => set("session_type")(event.target.value)}
        >
          <option value="">Any</option>
          {SESSION_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Symbol" htmlFor="paper-symbol">
        <Input
          id="paper-symbol"
          value={values.symbol}
          onChange={(event) => set("symbol")(event.target.value)}
        />
      </Field>
      <Field label="Account" htmlFor="paper-account">
        <Input
          id="paper-account"
          value={values.account_id}
          onChange={(event) => set("account_id")(event.target.value)}
        />
      </Field>
      <Field label="Strategy" htmlFor="paper-strategy">
        <Input
          id="paper-strategy"
          value={values.strategy_name}
          onChange={(event) => set("strategy_name")(event.target.value)}
        />
      </Field>
      <Field label="Model" htmlFor="paper-model">
        <Input
          id="paper-model"
          value={values.model_id}
          onChange={(event) => set("model_id")(event.target.value)}
        />
      </Field>
      <Field label="Started from" htmlFor="paper-from" hint="ISO timestamp">
        <Input
          id="paper-from"
          value={values.started_from}
          onChange={(event) => set("started_from")(event.target.value)}
        />
      </Field>
      <Field label="Started to" htmlFor="paper-to" hint="ISO timestamp">
        <Input
          id="paper-to"
          value={values.started_to}
          onChange={(event) => set("started_to")(event.target.value)}
        />
      </Field>
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
