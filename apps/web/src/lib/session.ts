/**
 * Where the bearer token lives in the browser.
 *
 * The token is held in a module-level variable and mirrored into
 * `sessionStorage` so a page refresh does not sign the user out. That choice
 * is a tradeoff worth stating plainly:
 *
 * * `sessionStorage` is scoped to one tab and cleared when it closes, unlike
 *   `localStorage`, which would survive indefinitely on a shared machine.
 * * Neither is safe against script injection. Any XSS on this origin can read
 *   the token, which is why the API sets `nosniff`, why responses tied to a
 *   token are `no-store`, and why the token is opaque and revocable rather
 *   than a self-describing credential.
 * * The safer end state is an httpOnly cookie the browser cannot read at all.
 *   That needs cookie handling and CSRF protection on the backend, which is
 *   more than a foundation sprint should quietly introduce.
 *
 * The token is never parsed. AQOS sessions are opaque server-side rows; there
 * is nothing inside to read, and code that tried would be assuming a JWT.
 */

export const SESSION_STORAGE_KEY = "aqos.session.token";

let token: string | null = null;

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    // A browser with storage disabled still gets a working in-memory session.
    return null;
  }
}

export function setSessionToken(value: string | null): void {
  token = value && value.trim() ? value : null;

  const store = storage();

  if (!store) {
    return;
  }

  try {
    if (token) {
      store.setItem(SESSION_STORAGE_KEY, token);
    } else {
      store.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {
    // Memory is still the source of truth, so a storage failure is survivable.
  }
}

export function getSessionToken(): string | null {
  if (token) {
    return token;
  }

  const store = storage();

  if (!store) {
    return null;
  }

  try {
    token = store.getItem(SESSION_STORAGE_KEY);
  } catch {
    token = null;
  }

  return token;
}

export function clearSessionToken(): void {
  setSessionToken(null);
}

/** Forget everything, for tests that must not leak state between cases. */
export function resetSessionForTests(): void {
  token = null;

  try {
    storage()?.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // Nothing to clean up.
  }
}
