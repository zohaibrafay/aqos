/**
 * Next.js configuration for the AQOS web foundation.
 *
 * Deliberately small. Anything the browser needs comes through the public
 * environment contract in `src/config/env.ts`, which is the one place that
 * decides what is safe to ship to a client.
 */
const nextConfig = {
  reactStrictMode: true,
  // The bundle carries no server secrets, so nothing is proxied or rewritten
  // here; the browser talks to the AQOS API directly at its configured origin.
  poweredByHeader: false,
};

export default nextConfig;
