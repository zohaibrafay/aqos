/**
 * The three answers every data view owes a user: loading, empty, or broken.
 *
 * Kept apart from the data components so "nothing yet", "nothing at all" and
 * "something went wrong" can never be rendered as the same blank panel.
 */

import type { ReactNode } from "react";

import { Badge } from "@/components/ui";
import type { AqosApiError } from "@/api/errors";

export function LoadingState({ label = "Loading…" }: { readonly label?: string }) {
  return (
    <div role="status" aria-live="polite" className="p-6 text-sm text-muted">
      {label}
    </div>
  );
}

export function EmptyState({
  title,
  description,
}: {
  readonly title: string;
  readonly description?: string;
}) {
  return (
    <div className="rounded border border-dashed border-edge p-6 text-center">
      <p className="text-sm text-slate-200">{title}</p>
      {description ? <p className="mt-1 text-xs text-muted">{description}</p> : null}
    </div>
  );
}

/**
 * One failure, shown honestly.
 *
 * The request id is displayed rather than hidden: it is the only thing a user
 * can quote that lets somebody find the matching server log, and an error
 * screen without it turns every report into a guess.
 */
export function ErrorMessage({
  error,
  children,
}: {
  readonly error: AqosApiError;
  readonly children?: ReactNode;
}) {
  return (
    <div role="alert" className="rounded border border-rose-800 bg-rose-950/40 p-4">
      <div className="flex items-center gap-2">
        <Badge tone="bad">{error.code}</Badge>
        {error.retryAfterSeconds !== null ? (
          <span className="text-xs text-muted">
            Retry in {error.retryAfterSeconds}s
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-sm text-slate-100">{error.message}</p>
      {error.requestId ? (
        <p className="mt-2 text-xs text-muted">
          Reference: <code data-testid="request-id">{error.requestId}</code>
        </p>
      ) : null}
      {children}
    </div>
  );
}

export function Alert({
  tone = "warn",
  children,
}: {
  readonly tone?: "warn" | "info";
  readonly children: ReactNode;
}) {
  const styles =
    tone === "warn"
      ? "border-amber-800 bg-amber-950/40 text-amber-100"
      : "border-sky-800 bg-sky-950/40 text-sky-100";

  return <div className={`rounded border p-3 text-sm ${styles}`}>{children}</div>;
}
