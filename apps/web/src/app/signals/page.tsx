import { EmptyState } from "@/components/states";
import { Card, PageHeader } from "@/components/ui";

/**
 * Signals placeholder.
 *
 * Sprint 063 builds the shell. The data view arrives with its own sprint, so
 * this page states plainly that there is nothing here yet rather than
 * rendering an empty table that looks like a user with no signals.
 */
export default function SignalsPage() {
  return (
    <>
      <PageHeader title="Signals" description="Trading signals and their lifecycle." />
      <Card>
        <EmptyState
          title="Not built yet"
          description="This screen arrives in a later sprint. Nothing is missing from your account."
        />
      </Card>
    </>
  );
}
