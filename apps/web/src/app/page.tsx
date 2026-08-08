import Link from "next/link";

import { Card, PageHeader } from "@/components/ui";

export default function HomePage() {
  return (
    <>
      <PageHeader
        title="AQOS"
        description="Research, paper trading and backtesting, behind one API."
      />
      <Card title="Getting started">
        <p className="text-sm text-muted">
          Sign in to reach your signals, accounts, paper sessions and backtests.
        </p>
        <Link
          href="/login"
          className="mt-3 inline-block text-sm text-sky-400 hover:text-sky-300"
        >
          Go to sign in
        </Link>
      </Card>
    </>
  );
}
