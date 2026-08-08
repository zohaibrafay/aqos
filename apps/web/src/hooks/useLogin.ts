"use client";

import { useCallback, useState } from "react";

import { auth } from "@/api/resources";
import { AqosApiError, isAqosApiError } from "@/api/errors";
import { getApiClient } from "@/lib/api";
import { setSessionToken } from "@/lib/session";
import type { SessionUser } from "@/api/types";

/**
 * The state behind the sign-in form.
 *
 * Plumbing only: it sends credentials, stores the returned opaque token and
 * reports failure in the API's own terms. It never inspects the token, and it
 * never decides what a caller may then do — the server does that on every
 * subsequent request.
 */

export interface LoginState {
  readonly pending: boolean;
  readonly error: AqosApiError | null;
  readonly user: SessionUser | null;
}

export function useLogin() {
  const [state, setState] = useState<LoginState>({
    pending: false,
    error: null,
    user: null,
  });

  const submit = useCallback(async (email: string, password: string) => {
    setState({ pending: true, error: null, user: null });

    try {
      const result = await auth.login(getApiClient(), email, password, "aqos-web");

      setSessionToken(result.token);
      setState({ pending: false, error: null, user: result.user });

      return result.user;
    } catch (cause) {
      // Anything that is not an API error is still shown as one, so the form
      // has a single failure shape to render.
      const error = isAqosApiError(cause)
        ? cause
        : new AqosApiError({
            code: "unreadable_response",
            message: "Sign in failed for an unknown reason.",
            status: 0,
          });

      setState({ pending: false, error, user: null });

      return null;
    }
  }, []);

  return { ...state, submit };
}
