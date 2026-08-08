"use client";

import type { AqosApiError } from "@/api/errors";
import { ErrorMessage } from "@/components/states";
import { Button } from "@/components/ui";

/**
 * One failure, with a way forward.
 *
 * Retrying is offered only when the server said the failure was temporary;
 * a retry button on a 403 would invite a user to keep trying something that
 * will never work.
 */
export function ApiErrorPanel({
  error,
  onRetry,
}: {
  readonly error: AqosApiError;
  readonly onRetry?: () => void;
}) {
  return (
    <ErrorMessage error={error}>
      {onRetry && error.isRetryable ? (
        <div className="mt-3">
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : null}
    </ErrorMessage>
  );
}
