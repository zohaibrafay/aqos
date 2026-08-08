/**
 * The application's single API client instance.
 *
 * Built from the public configuration and wired to the session store, so no
 * component ever constructs its own client or decides how a token is attached.
 */

import { AqosApiClient } from "@/api/client";
import { loadAqosWebConfig } from "@/config/env";
import { getSessionToken } from "@/lib/session";

let client: AqosApiClient | null = null;

export function getApiClient(): AqosApiClient {
  if (!client) {
    client = new AqosApiClient({
      baseUrl: loadAqosWebConfig().apiBaseUrl,
      getToken: getSessionToken,
    });
  }

  return client;
}

/** Drop the cached client, for tests that change configuration. */
export function resetApiClientForTests(): void {
  client = null;
}
