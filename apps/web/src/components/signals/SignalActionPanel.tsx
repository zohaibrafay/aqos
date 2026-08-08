"use client";

import { useState } from "react";

import { signalActions, type SignalActionName } from "@/api/resources";
import type { AqosApiError } from "@/api/errors";
import { isAqosApiError, AqosApiError as ApiError } from "@/api/errors";
import type { SignalDetail } from "@/api/types";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Alert } from "@/components/states";
import { Button, Card, Field, Input, Select } from "@/components/ui";
import { getApiClient } from "@/lib/api";

/**
 * Lifecycle decisions, taken deliberately.
 *
 * These change what a signal *means* — approved, rejected, missed, expired,
 * cancelled — and nothing about what happens next. No order is placed, no
 * account is touched and no broker is contacted; that is a different concern
 * with its own safety rails and it is not reachable from here.
 *
 * The server is the only authority on whether a transition is legal. Buttons
 * are enabled from a client-side hint so the common case reads well, but a
 * refusal from the API is always shown rather than pre-empted, and no status
 * changes on screen until the server has confirmed it.
 */

/**
 * Reason codes a person may choose when refusing a signal.
 *
 * Taken verbatim from the Sprint 045 taxonomy — nothing here is invented. The
 * server validates the code against the target status regardless, so a wrong
 * choice is refused rather than recorded.
 */
export const REJECT_REASON_CODES = [
  "manual_rejection",
  "confidence_below_threshold",
  "spread_too_high",
  "market_closed",
  "risk_limit_exceeded",
  "unpromoted_model",
  "duplicate_signal",
  "symbol_blocked",
  "validation_failed",
] as const;

export const MISS_REASON_CODES = [
  "approval_timeout",
  "expired_before_approval",
  "execution_window_closed",
  "signal_arrived_late",
  "broker_disconnected",
  "account_not_ready",
  "system_paused",
] as const;

/**
 * Which actions look available from a given status.
 *
 * A hint for the interface only. It mirrors the Sprint 044 transition table so
 * a caller is not invited to press something that cannot work, but the server
 * decides, and a stale hint produces a clean 409 rather than a wrong outcome.
 */
export const ACTIONS_BY_STATUS: Record<string, readonly SignalActionName[]> = {
  generated: ["approve", "mark-pending-approval", "reject", "miss", "expire", "cancel"],
  pending_approval: ["approve", "reject", "miss", "expire", "cancel"],
  approved: ["miss", "expire", "cancel"],
  rejected: [],
  missed: [],
  expired: [],
  executed: [],
  failed: [],
  cancelled: [],
};

/** Actions that end a signal's life and therefore need confirming. */
export const CONFIRMED_ACTIONS: readonly SignalActionName[] = [
  "reject",
  "miss",
  "expire",
  "cancel",
];

const ACTION_LABELS: Record<SignalActionName, string> = {
  approve: "Approve",
  reject: "Reject",
  miss: "Mark missed",
  expire: "Expire",
  cancel: "Cancel signal",
  "mark-pending-approval": "Send for approval",
};

const ALL_ACTIONS: readonly SignalActionName[] = [
  "approve",
  "mark-pending-approval",
  "reject",
  "miss",
  "expire",
  "cancel",
];

function toApiError(cause: unknown): AqosApiError {
  return isAqosApiError(cause)
    ? cause
    : new ApiError({
        code: "unreadable_response",
        message: "The action failed for an unknown reason.",
        status: 0,
      });
}

export function SignalActionPanel({
  signal,
  onCompleted,
}: {
  readonly signal: SignalDetail;
  readonly onCompleted: () => void;
}) {
  const [pending, setPending] = useState<SignalActionName | null>(null);
  const [confirming, setConfirming] = useState<SignalActionName | null>(null);
  const [reasonCode, setReasonCode] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<AqosApiError | null>(null);
  const [validation, setValidation] = useState<string | null>(null);

  const available = ACTIONS_BY_STATUS[signal.status] ?? [];
  const busy = pending !== null;

  const reset = () => {
    setConfirming(null);
    setReasonCode("");
    setNote("");
    setValidation(null);
  };

  const run = async (action: SignalActionName) => {
    setError(null);
    setValidation(null);

    // Checked here so a caller is told what is missing without a round trip;
    // the API requires both regardless.
    if ((action === "reject" || action === "miss") && !reasonCode) {
      setValidation("Choose a reason code.");

      return;
    }

    if (action === "cancel" && !note.trim()) {
      setValidation("Say why this signal is being cancelled.");

      return;
    }

    setPending(action);

    try {
      const client = getApiClient();

      if (action === "approve") {
        await signalActions.approve(client, signal.signal_id);
      } else if (action === "mark-pending-approval") {
        await signalActions.markPendingApproval(client, signal.signal_id);
      } else if (action === "reject") {
        await signalActions.reject(client, signal.signal_id, reasonCode);
      } else if (action === "miss") {
        await signalActions.miss(client, signal.signal_id, reasonCode);
      } else if (action === "expire") {
        await signalActions.expire(client, signal.signal_id);
      } else {
        await signalActions.cancel(client, signal.signal_id, note.trim());
      }

      reset();
      // Nothing on screen moves until this refetch returns the server's own
      // view. An optimistic status would show an outcome that may not have
      // happened.
      onCompleted();
    } catch (cause) {
      setError(toApiError(cause));
    } finally {
      setPending(null);
    }
  };

  const start = (action: SignalActionName) => {
    setError(null);
    setValidation(null);

    if (CONFIRMED_ACTIONS.includes(action)) {
      setReasonCode("");
      setNote("");
      setConfirming(action);

      return;
    }

    void run(action);
  };

  return (
    <Card title="Lifecycle actions">
      <p className="mb-3 text-xs text-muted">
        These record a decision about the signal. They place no order and reach
        no broker.
      </p>

      <div className="flex flex-wrap gap-2">
        {ALL_ACTIONS.map((action) => {
          const enabled = available.includes(action);

          return (
            <Button
              key={action}
              variant={action === "approve" ? "primary" : "secondary"}
              disabled={!enabled || busy}
              aria-disabled={!enabled || busy}
              title={
                enabled
                  ? undefined
                  : `Not available while the signal is ${signal.status}.`
              }
              onClick={() => start(action)}
            >
              {pending === action ? "Working…" : ACTION_LABELS[action]}
            </Button>
          );
        })}
      </div>

      {available.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          This signal is {signal.status}, which is final. Nothing can move it.
        </p>
      ) : null}

      {confirming ? (
        <div
          role="dialog"
          aria-label={`Confirm ${ACTION_LABELS[confirming]}`}
          className="mt-4 rounded border border-edge bg-surface p-4"
        >
          <h3 className="text-sm font-semibold text-slate-100">
            {ACTION_LABELS[confirming]}
          </h3>

          {confirming === "expire" ? (
            <Alert tone="info">
              Expiring only works once the signal&apos;s expiry time has actually
              passed. To stop a live signal deliberately, cancel it instead.
            </Alert>
          ) : null}

          {confirming === "reject" || confirming === "miss" ? (
            <div className="mt-3">
              <Field label="Reason code" htmlFor="reason-code">
                <Select
                  id="reason-code"
                  value={reasonCode}
                  onChange={(event) => setReasonCode(event.target.value)}
                >
                  <option value="">Choose a reason…</option>
                  {(confirming === "reject"
                    ? REJECT_REASON_CODES
                    : MISS_REASON_CODES
                  ).map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </Select>
              </Field>
              <p className="mt-1 text-xs text-muted">
                The category and severity are decided by the reason code on the
                server. They are not yours to set.
              </p>
            </div>
          ) : null}

          {confirming === "cancel" ? (
            <div className="mt-3">
              <Field label="Why?" htmlFor="cancel-note">
                <Input
                  id="cancel-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
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

          <div className="mt-4 flex gap-2">
            <Button disabled={busy} onClick={() => void run(confirming)}>
              {busy ? "Working…" : `Confirm ${ACTION_LABELS[confirming].toLowerCase()}`}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={reset}>
              Back
            </Button>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="mt-4">
          <ApiErrorPanel error={error} />
          {error.status === 409 ? (
            <p className="mt-2 text-xs text-muted">
              The server refused this transition. Check the signal&apos;s current
              status above; a signal that has already finished cannot move again.
            </p>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
