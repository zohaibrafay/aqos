/**
 * The public configuration contract.
 *
 * Every value here is compiled into the browser bundle, so this module decides
 * what is safe to ship rather than reading `process.env` at each call site.
 * Nothing secret may pass through it, and the names are checked against a
 * deny-list so a mistake fails loudly at startup instead of quietly shipping a
 * credential to every visitor.
 */

export const AQOS_WEB_CONFIG_VERSION = "1.0";

export type AqosWebEnvironment = "development" | "test" | "staging" | "production";

const ENVIRONMENTS: readonly AqosWebEnvironment[] = [
  "development",
  "test",
  "staging",
  "production",
];

/** Environments where a localhost API would mean the app is pointed nowhere real. */
const REMOTE_ENVIRONMENTS: readonly AqosWebEnvironment[] = ["staging", "production"];

/**
 * Fragments that must never appear in a public variable name.
 *
 * Next.js ships anything prefixed `NEXT_PUBLIC_`, so a variable called
 * `NEXT_PUBLIC_DB_PASSWORD` would be readable by every visitor. Rejecting the
 * name is cheaper than discovering the leak later.
 */
export const FORBIDDEN_CONFIG_FRAGMENTS = [
  "SECRET",
  "PASSWORD",
  "TOKEN",
  "CREDENTIAL",
  "PRIVATE_KEY",
  "DATABASE_URL",
  "DB_URL",
  "DSN",
  "API_KEY",
  "ACCESS_KEY",
] as const;

export interface AqosWebConfig {
  readonly apiBaseUrl: string;
  readonly appName: string;
  readonly environment: AqosWebEnvironment;
}

export class AqosWebConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AqosWebConfigError";
  }
}

/** Whether a public variable name looks like it carries a secret. */
export function isUnsafeConfigName(name: string): boolean {
  const upper = name.toUpperCase();

  return FORBIDDEN_CONFIG_FRAGMENTS.some((fragment) => upper.includes(fragment));
}

/**
 * Reject any public variable whose name suggests a secret.
 *
 * Checked across the whole `NEXT_PUBLIC_` namespace rather than only the
 * variables this app reads, because the bundle carries all of them regardless
 * of whether anything imports them.
 */
export function assertNoUnsafePublicNames(
  source: Record<string, string | undefined>,
): void {
  const offenders = Object.keys(source)
    .filter((name) => name.startsWith("NEXT_PUBLIC_"))
    .filter((name) => isUnsafeConfigName(name));

  if (offenders.length > 0) {
    throw new AqosWebConfigError(
      `These public variables look like secrets and would be readable by every ` +
        `visitor: ${offenders.sort().join(", ")}`,
    );
  }
}

function requireValue(
  source: Record<string, string | undefined>,
  name: string,
): string {
  const value = (source[name] ?? "").trim();

  if (!value) {
    throw new AqosWebConfigError(`${name} is required.`);
  }

  return value;
}

/**
 * Check the API origin is a usable absolute URL.
 *
 * A relative path or a bare hostname would send requests somewhere unintended,
 * and a trailing slash would produce double-slashed paths, so it is normalised
 * here once rather than defended against at every call site.
 */
export function normalizeApiBaseUrl(value: string): string {
  let parsed: URL;

  try {
    parsed = new URL(value);
  } catch {
    throw new AqosWebConfigError(
      "The API base URL must be an absolute URL including its scheme and host.",
    );
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new AqosWebConfigError("The API base URL must be http or https.");
  }

  return `${parsed.origin}${parsed.pathname.replace(/\/+$/, "")}`;
}

function parseEnvironment(value: string): AqosWebEnvironment {
  const candidate = value.trim().toLowerCase() as AqosWebEnvironment;

  if (!ENVIRONMENTS.includes(candidate)) {
    throw new AqosWebConfigError(
      `Unknown environment: ${value}. Expected one of ${ENVIRONMENTS.join(", ")}.`,
    );
  }

  return candidate;
}

function isLocalHost(hostname: string): boolean {
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1" ||
    hostname === "0.0.0.0"
  );
}

/**
 * Build the configuration, or refuse to start.
 *
 * A deployed build pointed at localhost is a misconfiguration that looks like
 * a working app until every request fails, so it is refused here where the
 * message can say why.
 */
export function loadAqosWebConfig(
  source: Record<string, string | undefined> = process.env as Record<
    string,
    string | undefined
  >,
): AqosWebConfig {
  assertNoUnsafePublicNames(source);

  const apiBaseUrl = normalizeApiBaseUrl(
    requireValue(source, "NEXT_PUBLIC_AQOS_WEB_API_BASE_URL"),
  );
  const environment = parseEnvironment(
    requireValue(source, "NEXT_PUBLIC_AQOS_WEB_ENV"),
  );
  const appName = (source["NEXT_PUBLIC_AQOS_WEB_APP_NAME"] ?? "AQOS").trim();

  if (
    REMOTE_ENVIRONMENTS.includes(environment) &&
    isLocalHost(new URL(apiBaseUrl).hostname)
  ) {
    throw new AqosWebConfigError(
      `A ${environment} build cannot point at ${apiBaseUrl}: it would look ` +
        "healthy while every request failed.",
    );
  }

  return { apiBaseUrl, appName, environment };
}
