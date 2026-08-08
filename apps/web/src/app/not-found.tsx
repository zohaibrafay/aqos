import Link from "next/link";

import { EmptyState } from "@/components/states";
import { PageHeader } from "@/components/ui";

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        title="There is nothing at this address."
        description="Check the link, or return to the dashboard."
      />
      <Link
        href="/dashboard"
        className="mt-4 inline-block text-sm text-sky-400 hover:text-sky-300"
      >
        Back to dashboard
      </Link>
    </>
  );
}
