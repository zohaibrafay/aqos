"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/**
 * The frame every page sits in.
 *
 * Navigation is a plain list of links. Nothing here performs an action, so the
 * shell cannot become a place where trading happens by accident.
 */

export interface NavItem {
  readonly href: string;
  readonly label: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/signals", label: "Signals" },
  { href: "/accounts", label: "Accounts" },
  { href: "/paper", label: "Paper" },
  { href: "/backtests", label: "Backtests" },
];

export function AppShell({
  appName,
  children,
}: {
  readonly appName: string;
  readonly children: ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-surface text-slate-100">
      <header className="border-b border-edge">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <Link href="/" className="text-sm font-semibold tracking-wide">
            {appName}
          </Link>
          <nav aria-label="Main" className="flex gap-4 text-sm">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname === item.href ? "page" : undefined}
                className={
                  pathname === item.href
                    ? "text-slate-100"
                    : "text-muted hover:text-slate-100"
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <Link href="/login" className="ml-auto text-sm text-muted hover:text-slate-100">
            Sign in
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
