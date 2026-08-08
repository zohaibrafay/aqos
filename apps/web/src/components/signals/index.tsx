"use client";

import Link from "next/link";

import type {
  PromotionStatus,
  SignalDetail,
  SignalEvent,
  SignalReason,
  SignalSummary,
} from "@/api/types";
import { Badge, Card, TableShell } from "@/components/ui";
import { EmptyState } from "@/components/states";
import type { BadgeTone } from "@/components/ui";

/**
 * Signal-specific presentation.
 *
 * Read-only throughout. Nothing here submits anything: the lifecycle action
 * controls are a separate concern and are deliberately absent from this sprint.
 */

/** A timestamp a person can read, or an explicit dash when there is none. */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    // Better to show what the server sent than to print "Invalid Date".
    return value;
  }

  return parsed.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
}

/** A confidence, or an explicit dash. Never 0, which would be a measurement. */
export function formatConfidence(value: number | null | undefined): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—";
}

const STATUS_TONES: Record<string, BadgeTone> = {
  generated: "neutral",
  pending_approval: "warn",
  approved: "good",
  executed: "good",
  rejected: "bad",
  failed: "bad",
  missed: "warn",
  expired: "warn",
  cancelled: "neutral",
};

export function SignalStatusBadge({ status }: { readonly status: string }) {
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{status}</Badge>;
}

export function SignalActionBadge({ action }: { readonly action: string }) {
  const tone: BadgeTone =
    action === "buy" ? "good" : action === "sell" ? "bad" : "neutral";

  return <Badge tone={tone}>{action}</Badge>;
}

export function SignalSourceBadge({ source }: { readonly source: string }) {
  return <Badge tone="neutral">{source}</Badge>;
}

/**
 * Promotion, shown for what it is.
 *
 * `unknown` gets its own appearance and its own words. Rendering it as "not
 * promoted" would turn "nobody has reviewed this" into a finding, and
 * rendering it as promoted would be a claim the registry never made.
 */
export function PromotionStatusBadge({
  status,
}: {
  readonly status: PromotionStatus;
}) {
  if (status.state === "promoted") {
    return <Badge tone="good">promoted</Badge>;
  }

  if (status.state === "not_promoted") {
    return <Badge tone="bad">not promoted</Badge>;
  }

  return <Badge tone="warn">unknown</Badge>;
}

export function SignalListTable({
  items,
}: {
  readonly items: readonly SignalSummary[];
}) {
  return (
    <TableShell
      columns={["Signal", "Symbol", "Action", "Status", "Source", "Confidence", "Generated"]}
    >
      {items.map((signal) => (
        <tr key={signal.signal_id} className="border-b border-edge/60">
          <td className="px-3 py-2">
            <Link
              href={`/signals/${signal.signal_id}`}
              className="text-sky-400 hover:text-sky-300"
            >
              {signal.signal_id.slice(0, 18)}
            </Link>
          </td>
          <td className="px-3 py-2">{signal.symbol}</td>
          <td className="px-3 py-2">
            <SignalActionBadge action={signal.action} />
          </td>
          <td className="px-3 py-2">
            <SignalStatusBadge status={signal.status} />
          </td>
          <td className="px-3 py-2">
            <SignalSourceBadge source={signal.source} />
          </td>
          <td className="px-3 py-2">{formatConfidence(signal.confidence)}</td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(signal.generated_at_utc)}
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function DetailRow({
  label,
  value,
}: {
  readonly label: string;
  readonly value: string | number | null | undefined;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-edge/40 py-1.5 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-slate-100">
        {value === null || value === undefined || value === "" ? "—" : value}
      </span>
    </div>
  );
}

/**
 * One signal's safe fields.
 *
 * `extra_metadata` is not shown because the API does not return it, and no
 * internal or ORM field appears here either.
 */
export function SignalDetailCard({ signal }: { readonly signal: SignalDetail }) {
  return (
    <Card title="Signal">
      <DetailRow label="Signal ID" value={signal.signal_id} />
      <DetailRow label="Symbol" value={signal.symbol} />
      <DetailRow label="Timeframe" value={signal.timeframe} />
      <DetailRow label="Action" value={signal.action} />
      <DetailRow label="Source" value={signal.source} />
      <DetailRow label="Status" value={signal.status} />
      <DetailRow label="Confidence" value={formatConfidence(signal.confidence)} />
      <DetailRow label="Strategy" value={signal.strategy_name} />
      <DetailRow label="Model" value={signal.model_id} />
      <DetailRow label="Model version" value={signal.model_version} />
      <DetailRow label="Generated" value={formatTimestamp(signal.generated_at_utc)} />
      <DetailRow label="Expires" value={formatTimestamp(signal.expires_at_utc)} />
      <DetailRow label="Status reason" value={signal.status_reason} />
    </Card>
  );
}

/** The lifecycle audit trail, oldest first, exactly as the API returns it. */
export function SignalEventsTimeline({
  events,
}: {
  readonly events: readonly SignalEvent[];
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No lifecycle events"
        description="Nothing has moved this signal yet."
      />
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {events.map((event) => (
        <li key={event.event_id} className="border-l-2 border-edge pl-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted">{event.from_status ?? "created"}</span>
            <span aria-hidden="true" className="text-muted">
              →
            </span>
            <SignalStatusBadge status={event.to_status} />
          </div>
          <p className="mt-1 text-xs text-muted">
            {formatTimestamp(event.occurred_at_utc)}
            {event.actor ? ` · ${event.actor}` : ""}
          </p>
          {event.reason ? (
            <p className="mt-1 text-sm text-slate-200">{event.reason}</p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

const SEVERITY_TONES: Record<string, BadgeTone> = {
  informational: "neutral",
  warning: "warn",
  blocking: "bad",
  critical: "bad",
};

/**
 * Structured reasons from the taxonomy.
 *
 * The category and the severity are shown as the server resolved them. They
 * are read-only here in the strongest sense: there is no control to change
 * either, because the code alone decides both.
 */
export function SignalReasonsPanel({
  reasons,
}: {
  readonly reasons: readonly SignalReason[];
}) {
  if (reasons.length === 0) {
    return (
      <EmptyState
        title="No structured reasons"
        description="This signal has not been rejected, missed or failed."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {reasons.map((reason) => (
        <li key={reason.reason_id} className="rounded border border-edge p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">{reason.reason_code}</Badge>
            <Badge tone="neutral">{reason.reason_category}</Badge>
            <Badge tone={SEVERITY_TONES[reason.severity] ?? "neutral"}>
              {reason.severity}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-slate-100">{reason.message}</p>
          <p className="mt-1 text-xs text-muted">
            {formatTimestamp(reason.created_at_utc)}
            {reason.source ? ` · ${reason.source}` : ""}
          </p>
        </li>
      ))}
    </ul>
  );
}
