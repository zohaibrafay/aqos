"use client";

import { useCallback, useEffect, useState } from "react";

import { AqosApiError, isAqosApiError } from "@/api/errors";

/**
 * One fetch, with the three outcomes a view has to distinguish.
 *
 * `loading`, `error` and `data` are separate rather than collapsed, so
 * "still loading", "failed" and "loaded, and there is nothing" can never be
 * rendered as the same blank panel.
 */

export interface ApiResourceState<T> {
  readonly data: T | null;
  readonly error: AqosApiError | null;
  readonly loading: boolean;
}

function toApiError(cause: unknown): AqosApiError {
  return isAqosApiError(cause)
    ? cause
    : new AqosApiError({
        code: "unreadable_response",
        message: "The request failed for an unknown reason.",
        status: 0,
      });
}

export function useApiResource<T>(
  load: () => Promise<T>,
  deps: readonly unknown[],
): ApiResourceState<T> & { readonly reload: () => void } {
  const [state, setState] = useState<ApiResourceState<T>>({
    data: null,
    error: null,
    loading: true,
  });
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    let active = true;

    setState({ data: null, error: null, loading: true });

    load()
      .then((data) => {
        if (active) {
          setState({ data, error: null, loading: false });
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setState({ data: null, error: toApiError(cause), loading: false });
        }
      });

    return () => {
      active = false;
    };
    // Keyed on the caller's own dependencies rather than on `load`, which
    // is rebuilt every render and would refetch forever. `nonce` is what
    // makes an explicit reload re-run this.
  }, [...deps, nonce]);

  return { ...state, reload };
}
