"use client";

import { useState } from "react";

import {
  PAPER_REASON_REQUIRED,
  PAPER_SESSION_ACTIONS,
  paperActions,
  type PaperOrderOutcome,
  type PaperSessionActionName,
} from "@/api/resources";
import { AqosApiError, isAqosApiError } from "@/api/errors";
import type { PaperSessionDetail } from "@/api/types";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Alert } from "@/components/states";
import { Badge, Button, Card, Field, Input, Select } from "@/components/ui";
import {
  EMPTY_MARKET_BAR,
  parseNumber,
  validateMarketBar,
  type MarketBarValues,
} from "@/components/paper/validation";
import { getApiClient } from "@/lib/api";

/**
 * Controls for a simulated run.
 *
 * Everything here is paper. No control reaches a venue, no wording implies one
 * did, and nothing on screen changes until the server has confirmed it. A
 * refused order is shown as what it is — an audited refusal — rather than as a
 * failure, because the attempt happened and was recorded.
 */

export function toApiError(cause: unknown): AqosApiError {
  return isAqosApiError(cause)
    ? cause
    : new AqosApiError({
        code: "unreadable_response",
        message: "The action failed for an unknown reason.",
        status: 0,
      });
}

/** Which commands a status looks ready for. A hint; the server decides. */
export const PAPER_ACTIONS_BY_STATUS: Record<
  string,
  readonly PaperSessionActionName[]
> = {
  created: ["start", "cancel", "fail"],
  running: ["pause", "complete", "cancel", "fail"],
  paused: ["resume", "cancel", "fail"],
  completed: [],
  failed: [],
  cancelled: [],
};

/** Commands that end a run, or stop one mid-flight, need confirming. */
export const CONFIRMED_PAPER_ACTIONS: readonly PaperSessionActionName[] = [
  "complete",
  "cancel",
  "fail",
];

const ACTION_LABELS: Record<PaperSessionActionName, string> = {
  start: "Start run",
  pause: "Pause",
  resume: "Resume",
  complete: "Complete run",
  cancel: "Cancel run",
  fail: "Mark failed",
};

export function ConfirmationDialog({
  title,
  children,
  busy,
  onConfirm,
  onCancel,
  confirmLabel,
}: {
  readonly title: string;
  readonly children?: React.ReactNode;
  readonly busy: boolean;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
  readonly confirmLabel: string;
}) {
  return (
    <div
      role="dialog"
      aria-label={title}
      className="mt-4 rounded border border-edge bg-surface p-4"
    >
      <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      {children}
      <div className="mt-4 flex gap-2">
        <Button disabled={busy} onClick={onConfirm}>
          {busy ? "Working…" : confirmLabel}
        </Button>
        <Button variant="secondary" disabled={busy} onClick={onCancel}>
          Back
        </Button>
      </div>
    </div>
  );
}

export function PaperSessionActionsPanel({
  session,
  onCompleted,
}: {
  readonly session: PaperSessionDetail;
  readonly onCompleted: () => void;
}) {
  const [pending, setPending] = useState<PaperSessionActionName | null>(null);
  const [confirming, setConfirming] = useState<PaperSessionActionName | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<AqosApiError | null>(null);
  const [validation, setValidation] = useState<string | null>(null);

  const available = PAPER_ACTIONS_BY_STATUS[session.status] ?? [];
  const busy = pending !== null;

  const run = async (action: PaperSessionActionName) => {
    setError(null);
    setValidation(null);

    if (PAPER_REASON_REQUIRED.includes(action) && !reason.trim()) {
      setValidation("Say why this run is stopping.");

      return;
    }

    setPending(action);

    try {
      await paperActions.command(
        getApiClient(),
        session.session_id,
        action,
        reason.trim() || undefined,
      );

      setConfirming(null);
      setReason("");
      // Nothing moves on screen until this refetch returns the server's view.
      onCompleted();
    } catch (cause) {
      setError(toApiError(cause));
    } finally {
      setPending(null);
    }
  };

  return (
    <Card title="Run controls">
      <p className="mb-3 text-xs text-muted">
        These start and stop a simulated run. No order reaches a venue.
      </p>

      <div className="flex flex-wrap gap-2">
        {Object.values(PAPER_SESSION_ACTIONS).map((action) => {
          const enabled = available.includes(action);

          return (
            <Button
              key={action}
              variant={action === "start" ? "primary" : "secondary"}
              disabled={!enabled || busy}
              title={
                enabled ? undefined : `Not available while the run is ${session.status}.`
              }
              onClick={() => {
                setError(null);
                setValidation(null);
                setReason("");

                if (CONFIRMED_PAPER_ACTIONS.includes(action)) {
                  setConfirming(action);
                } else {
                  void run(action);
                }
              }}
            >
              {pending === action ? "Working…" : ACTION_LABELS[action]}
            </Button>
          );
        })}
      </div>

      {available.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          This run is {session.status}, which is final.
        </p>
      ) : null}

      {confirming ? (
        <ConfirmationDialog
          title={`Confirm ${ACTION_LABELS[confirming]}`}
          busy={busy}
          confirmLabel={`Confirm ${ACTION_LABELS[confirming].toLowerCase()}`}
          onConfirm={() => void run(confirming)}
          onCancel={() => {
            setConfirming(null);
            setReason("");
            setValidation(null);
          }}
        >
          {PAPER_REASON_REQUIRED.includes(confirming) ? (
            <div className="mt-3">
              <Field label="Why?" htmlFor="session-reason">
                <Input
                  id="session-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  maxLength={512}
                />
              </Field>
            </div>
          ) : null}
          {validation ? (
            <p role="alert" className="mt-3 text-sm text-rose-300">
              {validation}
            </p>
          ) : null}
        </ConfirmationDialog>
      ) : null}

      {error ? (
        <div className="mt-4">
          <ApiErrorPanel error={error} />
        </div>
      ) : null}
    </Card>
  );
}

export function MarketBarFields({
  values,
  onChange,
}: {
  readonly values: MarketBarValues;
  readonly onChange: (values: MarketBarValues) => void;
}) {
  const set = (key: keyof MarketBarValues) => (value: string) =>
    onChange({ ...values, [key]: value });

  return (
    <fieldset className="mt-3 rounded border border-edge p-3">
      <legend className="px-1 text-xs text-muted">
        Simulated market bar — the prices this order is filled against
      </legend>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Open" htmlFor="bar-open">
          <Input
            id="bar-open"
            value={values.open}
            onChange={(event) => set("open")(event.target.value)}
          />
        </Field>
        <Field label="High" htmlFor="bar-high">
          <Input
            id="bar-high"
            value={values.high}
            onChange={(event) => set("high")(event.target.value)}
          />
        </Field>
        <Field label="Low" htmlFor="bar-low">
          <Input
            id="bar-low"
            value={values.low}
            onChange={(event) => set("low")(event.target.value)}
          />
        </Field>
        <Field label="Close" htmlFor="bar-close">
          <Input
            id="bar-close"
            value={values.close}
            onChange={(event) => set("close")(event.target.value)}
          />
        </Field>
        <Field label="Bar timestamp" htmlFor="bar-timestamp" hint="ISO timestamp">
          <Input
            id="bar-timestamp"
            value={values.timestamp_utc}
            onChange={(event) => set("timestamp_utc")(event.target.value)}
          />
        </Field>
        <Field label="Volume" htmlFor="bar-volume" hint="Optional">
          <Input
            id="bar-volume"
            value={values.volume}
            onChange={(event) => set("volume")(event.target.value)}
          />
        </Field>
      </div>
    </fieldset>
  );
}

/**
 * A refusal the gate recorded.
 *
 * Shown as an outcome rather than an error: the attempt reached the rule gate,
 * the gate said no, and that decision is stored and explainable. Rendering it
 * as a failure would suggest something broke.
 */
export function AuditedRefusalPanel({
  outcome,
}: {
  readonly outcome: PaperOrderOutcome;
}) {
  return (
    <div
      data-testid="audited-refusal"
      className="mt-4 rounded border border-amber-800 bg-amber-950/40 p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="warn">refused</Badge>
        {outcome.decision.primary_reason_code ? (
          <Badge tone="neutral">{outcome.decision.primary_reason_code}</Badge>
        ) : null}
      </div>
      <p className="mt-2 text-sm text-slate-100">
        {outcome.rejection_message ??
          "The rule gate refused this order. The decision has been recorded."}
      </p>
      <p className="mt-1 text-xs text-muted">
        Nothing was filled. This refusal is stored with the run&apos;s decisions.
      </p>
    </div>
  );
}

export function PaperOrderSubmitForm({
  sessionId,
  onCompleted,
}: {
  readonly sessionId: string;
  readonly onCompleted: () => void;
}) {
  const [symbol, setSymbol] = useState("");
  const [action, setAction] = useState("buy");
  const [orderType, setOrderType] = useState("market");
  const [quantity, setQuantity] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [bar, setBar] = useState<MarketBarValues>(EMPTY_MARKET_BAR);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState<string | null>(null);
  const [error, setError] = useState<AqosApiError | null>(null);
  const [refusal, setRefusal] = useState<PaperOrderOutcome | null>(null);

  const check = (): string | null => {
    if (!symbol.trim()) {
      return "Enter a symbol.";
    }

    const size = parseNumber(quantity);

    if (size === null || size <= 0) {
      return "Enter a quantity greater than zero.";
    }

    return validateMarketBar(bar);
  };

  const submit = async () => {
    const problem = check();

    if (problem) {
      setValidation(problem);

      return;
    }

    setValidation(null);
    setError(null);
    setRefusal(null);
    setBusy(true);

    try {
      const outcome = await paperActions.submitOrder(getApiClient(), sessionId, {
        symbol: symbol.trim(),
        action,
        order_type: orderType,
        quantity: parseNumber(quantity) ?? 0,
        market: {
          symbol: symbol.trim(),
          timestamp_utc: bar.timestamp_utc.trim(),
          open: parseNumber(bar.open) ?? 0,
          high: parseNumber(bar.high) ?? 0,
          low: parseNumber(bar.low) ?? 0,
          close: parseNumber(bar.close) ?? 0,
          ...(parseNumber(bar.volume) === null
            ? {}
            : { volume: parseNumber(bar.volume) as number }),
        },
        ...(parseNumber(stopLoss) === null
          ? {}
          : { stop_loss: parseNumber(stopLoss) as number }),
        ...(parseNumber(takeProfit) === null
          ? {}
          : { take_profit: parseNumber(takeProfit) as number }),
      });

      setConfirming(false);

      if (!outcome.accepted) {
        setRefusal(outcome);
      }

      onCompleted();
    } catch (cause) {
      setError(toApiError(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Submit a simulated order">
      <p className="mb-3 text-xs text-muted">
        This books an order inside the simulator against the bar you supply. No
        venue is contacted and no real money moves.
      </p>

      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          setValidation(check());

          if (!check()) {
            setConfirming(true);
          }
        }}
      >
        <Field label="Symbol" htmlFor="order-symbol">
          <Input
            id="order-symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          />
        </Field>
        <Field label="Side" htmlFor="order-action">
          <Select
            id="order-action"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          >
            <option value="buy">buy</option>
            <option value="sell">sell</option>
            <option value="close">close</option>
          </Select>
        </Field>
        <Field label="Order type" htmlFor="order-type">
          <Select
            id="order-type"
            value={orderType}
            onChange={(event) => setOrderType(event.target.value)}
          >
            <option value="market">market</option>
            <option value="limit">limit</option>
          </Select>
        </Field>
        <Field label="Quantity" htmlFor="order-quantity">
          <Input
            id="order-quantity"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </Field>
        <Field label="Stop loss" htmlFor="order-stop" hint="Optional">
          <Input
            id="order-stop"
            value={stopLoss}
            onChange={(event) => setStopLoss(event.target.value)}
          />
        </Field>
        <Field label="Take profit" htmlFor="order-target" hint="Optional">
          <Input
            id="order-target"
            value={takeProfit}
            onChange={(event) => setTakeProfit(event.target.value)}
          />
        </Field>

        <div className="sm:col-span-2">
          <MarketBarFields values={bar} onChange={setBar} />
        </div>

        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            Review order
          </Button>
        </div>
      </form>

      {validation ? (
        <p role="alert" className="mt-3 text-sm text-rose-300">
          {validation}
        </p>
      ) : null}

      {confirming ? (
        <ConfirmationDialog
          title="Confirm simulated order"
          busy={busy}
          confirmLabel="Submit simulated order"
          onConfirm={() => void submit()}
          onCancel={() => setConfirming(false)}
        >
          <Alert tone="info">
            {action} {quantity} {symbol} against a bar closing at {bar.close}. This
            is a simulation.
          </Alert>
        </ConfirmationDialog>
      ) : null}

      {refusal ? <AuditedRefusalPanel outcome={refusal} /> : null}

      {error ? (
        <div className="mt-4">
          <ApiErrorPanel error={error} />
        </div>
      ) : null}
    </Card>
  );
}
