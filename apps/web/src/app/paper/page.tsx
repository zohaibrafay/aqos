import { EmptyState } from "@/components/states";
import { Card, PageHeader } from "@/components/ui";

/**
 * Paper placeholder.
 *
 * Sprint 063 builds the shell. The data view arrives with its own sprint, so
 * this page states plainly that there is nothing here yet rather than
 * rendering an empty table that looks like a user with no sessions.
 */
export default function PaperPage() {
  return (
    <>
      <PageHeader title="Paper" description="Simulated trading sessions and their results." />
      <Card>
        <EmptyState
          title="Not built yet"
          description="This screen arrives in a later sprint. Nothing is missing from your account."
        />
      </Card>
    </>
  );
}
