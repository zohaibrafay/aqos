"use client";

import Link from "next/link";

import type {
  PaperDecision,
  PaperFill,
  PaperOrder,
  PaperPosition,
  PaperSessionDetail,
  PaperSessionResult,
  PaperSessionSummary,
  PaperTrade,
} from "@/api/types";
import { MetricValue, ProfitFactorValue, formatPercent } from "@/components/accounts";
import { formatTimestamp } from "@/components/signals";
import { EmptyState } from "@/components/states";
import { Badge, Card, TableShell } from "@/components/ui";
import type { BadgeTone } from "@/components/ui";

/**
 * Paper trading presentation.
 *
 * Everything shown here is simulated. The wording says so wherever a reader
 * might otherwise assume money moved, because a screen that looks like a live
 * blotter is the easiest way for somebody to believe it is one.
 *
 * Read-only in this sprint: no control here starts a session, submits an order
 * or closes a position.
 */

const SESSION_TONES: Record<string, BadgeTone> = {
  created: "neutral",
  running: "good",
  paused: "warn",
  completed: "good",
  failed: "bad",
  cancelled: "neutral",
};

export function PaperSessionStatusBadge({ status }: { readonly status: string }) {
  return <Badge tone={SESSION_TONES[status] ?? "neutral"}>{status}</Badge>;
}

export function PaperSessionTypeBadge({ type }: { readonly type: string }) {
  return <Badge tone="neutral">{type}</Badge>;
}

/** A banner nobody has to look for. */
export function SimulatedNotice() {
  return (
    <p className="mb-4 rounded border border-edge bg-panel px-3 py-2 text-xs text-muted">
      Everything on this page is simulated. No order reached a venue and no real
      money moved.
    </p>
  );
}

export function PaperSessionListTable({
  items,
}: {
  readonly items: readonly PaperSessionSummary[];
}) {
  return (
    <TableShell
      columns={["Session", "Type", "Status", "Trades", "Net P&L", "Profit factor", "Started"]}
    >
      {items.map((session) => (
        <tr key={session.session_id} className="border-b border-edge/60">
          <td className="px-3 py-2">
            <Link
              href={`/paper/sessions/${session.session_id}`}
              className="text-sky-400 hover:text-sky-300"
            >
              {session.session_name}
            </Link>
          </td>
          <td className="px-3 py-2">
            <PaperSessionTypeBadge type={session.session_type} />
          </td>
          <td className="px-3 py-2">
            <PaperSessionStatusBadge status={session.status} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={session.total_trades} digits={0} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={session.net_pnl} />
          </td>
          <td className="px-3 py-2">
            <ProfitFactorValue
              value={session.profit_factor}
              state={session.profit_factor_state}
            />
          </td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(session.started_at_utc)}
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function Row({
  label,
  children,
}: {
  readonly label: string;
  readonly children: React.ReactNode;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-edge/40 py-1.5 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-slate-100">{children}</span>
    </div>
  );
}

export function PaperSessionDetailCard({
  session,
}: {
  readonly session: PaperSessionDetail;
}) {
  return (
    <Card title="Simulated session">
      <Row label="Name">{session.session_name}</Row>
      <Row label="Session ID">{session.session_id}</Row>
      <Row label="Account">{session.account_id}</Row>
      <Row label="Type">
        <PaperSessionTypeBadge type={session.session_type} />
      </Row>
      <Row label="Status">
        <PaperSessionStatusBadge status={session.status} />
      </Row>
      <Row label="Symbol">{session.symbol ?? "—"}</Row>
      <Row label="Timeframe">{session.timeframe ?? "—"}</Row>
      <Row label="Strategy">{session.strategy_name ?? "—"}</Row>
      <Row label="Model">{session.model_id ?? "—"}</Row>
      <Row label="Model version">{session.model_version ?? "—"}</Row>
      <Row label="Started">{formatTimestamp(session.started_at_utc)}</Row>
      <Row label="Ended">{formatTimestamp(session.ended_at_utc)}</Row>
      <Row label="Initial balance">
        <MetricValue value={session.initial_balance} />
      </Row>
      <Row label="Final balance">
        <MetricValue value={session.final_balance} />
      </Row>
      <Row label="Status reason">{session.status_reason ?? "—"}</Row>
    </Card>
  );
}

/**
 * What the run measured.
 *
 * A session with no trades reports that plainly rather than filling the panel
 * with zeros: nought trades and nought profit are different claims from "this
 * run never opened anything".
 */
export function PaperResultSummary({
  result,
}: {
  readonly result: PaperSessionResult;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="mb-2 text-xs uppercase text-muted">Activity</h3>
        <Row label="Orders">
          <MetricValue value={result.total_orders} digits={0} />
        </Row>
        <Row label="Fills">
          <MetricValue value={result.total_fills} digits={0} />
        </Row>
        <Row label="Trades">
          <MetricValue value={result.total_trades} digits={0} />
        </Row>
        <Row label="Symbols traded">
          {result.symbols_traded.length > 0 ? result.symbols_traded.join(", ") : "—"}
        </Row>
      </div>

      <div>
        <h3 className="mb-2 text-xs uppercase text-muted">Outcome</h3>
        {result.has_trades ? (
          <>
            <Row label="Winning trades">
              <MetricValue value={result.winning_trades} digits={0} />
            </Row>
            <Row label="Losing trades">
              <MetricValue value={result.losing_trades} digits={0} />
            </Row>
            <Row label="Win rate">{formatPercent(result.win_rate)}</Row>
            <Row label="Net P&L">
              <MetricValue value={result.net_pnl} />
            </Row>
            <Row label="Gross profit">
              <MetricValue value={result.gross_profit} />
            </Row>
            <Row label="Gross loss">
              <MetricValue value={result.gross_loss} />
            </Row>
            <Row label="Profit factor">
              <ProfitFactorValue
                value={result.profit_factor}
                state={result.profit_factor_state}
              />
            </Row>
            <Row label="Max drawdown">
              <MetricValue value={result.max_drawdown} />
            </Row>
            <Row label="Ending balance">
              <MetricValue value={result.ending_balance} />
            </Row>
          </>
        ) : (
          <p data-testid="no-trades" className="text-sm text-slate-200">
            This run booked no trades, so there is nothing to measure. That is
            not the same as a run that broke even.
          </p>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs uppercase text-muted">Decisions</h3>
        <Row label="Allowed">
          <MetricValue value={result.decisions_allowed} digits={0} />
        </Row>
        <Row label="Refused">
          <MetricValue value={result.decisions_rejected} digits={0} />
        </Row>
        <Row label="Refusal rate">{formatPercent(result.rejection_rate)}</Row>

        {result.top_rejection_reasons.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {result.top_rejection_reasons.map((reason) => (
              <li key={reason.reason_code}>
                <Badge tone="warn">
                  {reason.reason_code} × {reason.total}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function Table<T>({
  items,
  columns,
  empty,
  row,
}: {
  readonly items: readonly T[];
  readonly columns: readonly string[];
  readonly empty: string;
  readonly row: (item: T) => React.ReactNode;
}) {
  if (items.length === 0) {
    return <EmptyState title={empty} />;
  }

  return <TableShell columns={columns}>{items.map(row)}</TableShell>;
}

export function PaperOrdersTable({ items }: { readonly items: readonly PaperOrder[] }) {
  return (
    <Table
      items={items}
      empty="No simulated orders"
      columns={["Symbol", "Action", "Type", "Status", "Quantity", "Filled", "Avg price", "Refused because"]}
      row={(order) => (
        <tr key={order.order_id} className="border-b border-edge/60">
          <td className="px-3 py-2">{order.symbol}</td>
          <td className="px-3 py-2">{order.action}</td>
          <td className="px-3 py-2">{order.order_type}</td>
          <td className="px-3 py-2">
            <Badge tone={order.status === "rejected" ? "bad" : "neutral"}>
              {order.status}
            </Badge>
          </td>
          <td className="px-3 py-2">
            <MetricValue value={order.quantity} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={order.filled_quantity} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={order.average_fill_price} />
          </td>
          <td className="px-3 py-2 text-muted">{order.rejection_reason ?? "—"}</td>
        </tr>
      )}
    />
  );
}

export function PaperFillsTable({ items }: { readonly items: readonly PaperFill[] }) {
  return (
    <Table
      items={items}
      empty="No simulated fills"
      columns={["Order", "Quantity", "Price", "Commission", "Filled"]}
      row={(fill) => (
        <tr key={fill.fill_id} className="border-b border-edge/60">
          <td className="px-3 py-2">{fill.order_id.slice(0, 18)}</td>
          <td className="px-3 py-2">
            <MetricValue value={fill.quantity} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={fill.price} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={fill.commission} />
          </td>
          <td className="px-3 py-2 text-muted">{formatTimestamp(fill.filled_at_utc)}</td>
        </tr>
      )}
    />
  );
}

export function PaperPositionsTable({
  items,
}: {
  readonly items: readonly PaperPosition[];
}) {
  return (
    <Table
      items={items}
      empty="No simulated positions"
      columns={["Symbol", "Side", "Status", "Quantity", "Entry", "Realized P&L", "Closed"]}
      row={(position) => (
        <tr key={position.position_id} className="border-b border-edge/60">
          <td className="px-3 py-2">{position.symbol}</td>
          <td className="px-3 py-2">{position.side}</td>
          <td className="px-3 py-2">
            <Badge tone={position.status === "open" ? "good" : "neutral"}>
              {position.status}
            </Badge>
          </td>
          <td className="px-3 py-2">
            <MetricValue value={position.quantity} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={position.entry_price} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={position.realized_pnl} />
          </td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(position.closed_at_utc)}
          </td>
        </tr>
      )}
    />
  );
}

export function PaperTradesTable({ items }: { readonly items: readonly PaperTrade[] }) {
  return (
    <Table
      items={items}
      empty="No simulated trades"
      columns={["Symbol", "Side", "Entry", "Exit", "Net P&L", "Exit reason", "Closed"]}
      row={(trade) => (
        <tr key={trade.trade_id} className="border-b border-edge/60">
          <td className="px-3 py-2">{trade.symbol}</td>
          <td className="px-3 py-2">{trade.side}</td>
          <td className="px-3 py-2">
            <MetricValue value={trade.entry_price} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={trade.exit_price} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={trade.net_pnl} />
          </td>
          <td className="px-3 py-2 text-muted">{trade.exit_reason ?? "—"}</td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(trade.closed_at_utc)}
          </td>
        </tr>
      )}
    />
  );
}

/**
 * Why each attempt was allowed or refused.
 *
 * A refusal is an audited outcome, not a failure: the reason code is what makes
 * "why did nothing happen?" answerable without reading a server log.
 */
export function PaperDecisionsTable({
  items,
}: {
  readonly items: readonly PaperDecision[];
}) {
  return (
    <Table
      items={items}
      empty="No execution decisions"
      columns={["Symbol", "Outcome", "Reason", "Mode", "Decided"]}
      row={(decision) => (
        <tr key={decision.decision_id} className="border-b border-edge/60">
          <td className="px-3 py-2">{decision.symbol}</td>
          <td className="px-3 py-2">
            <Badge tone={decision.is_allowed ? "good" : "warn"}>
              {decision.is_allowed ? "allowed" : "refused"}
            </Badge>
          </td>
          <td className="px-3 py-2">
            {decision.primary_reason_code ? (
              <span className="text-slate-100">{decision.primary_reason_code}</span>
            ) : (
              <span className="text-muted">—</span>
            )}
            {decision.blocking_sources.length > 0 ? (
              <span className="ml-2 text-xs text-muted">
                {decision.blocking_sources.join(", ")}
              </span>
            ) : null}
          </td>
          <td className="px-3 py-2 text-muted">
            {decision.effective_execution_mode ?? "—"}
          </td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(decision.decided_at_utc)}
          </td>
        </tr>
      )}
    />
  );
}
