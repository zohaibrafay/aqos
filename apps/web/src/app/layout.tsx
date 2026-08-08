import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { loadAqosWebConfig } from "@/config/env";
import "@/styles/globals.css";

/**
 * Configuration is resolved once, at layout render.
 *
 * A misconfigured build fails here with a message that says which value is
 * wrong, rather than surfacing later as every request going nowhere.
 */
const config = loadAqosWebConfig();

export const metadata: Metadata = {
  title: config.appName,
  description: "AQOS research and execution console.",
};

export default function RootLayout({ children }: { readonly children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppShell appName={config.appName}>{children}</AppShell>
      </body>
    </html>
  );
}
