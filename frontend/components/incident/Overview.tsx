import { ArrowRight } from "lucide-react";
import type { IncidentResultsResponse, TimelineEntryResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Card, CardHeader, EmptyState } from "@/components/ui";

/**
 * Next-action copy is derived purely from the incident's own status enum
 * (app/models/incident_enums.py's IncidentStatus) - it's a direct
 * restatement of what that status means, not an AI-generated conclusion
 * or anything not already true of the incident.
 */
function nextActionFor(status: IncidentResultsResponse["incident"]["status"]): string {
  switch (status) {
    case "new":
      return "No investigation has been run yet. Start one from the Investigation tab.";
    case "investigating":
      return "An investigation is in progress.";
    case "diagnosed":
      return "A diagnosis is ready. Recommend a remediation from the Remediation tab.";
    case "awaiting_approval":
      return "A remediation is waiting on your approval in the Remediation tab.";
    case "remediating":
      return "The approved remediation is executing.";
    case "verifying":
      return "Checking whether the remediation resolved the incident.";
    case "resolved":
      return "Resolved - verification confirmed recovery.";
    case "unresolved":
      return "Investigation did not reach a confirmed fix.";
  }
}

export function OverviewTab({
  results,
  recentTimeline,
  onViewTimeline,
}: {
  results: IncidentResultsResponse;
  recentTimeline: TimelineEntryResponse[] | null;
  onViewTimeline: () => void;
}) {
  const { incident, hypotheses, diagnosis, remediations, approvals } = results;
  const pendingApprovals = approvals.filter((a) => a.status === "pending").length;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Summary" />
        <div className="px-5 py-4">
          <p className="text-sm text-ink-secondary">{incident.description || "No description was provided when this incident was opened."}</p>
          <p className="mt-3 rounded-md border border-accent/30 bg-accent-muted px-3.5 py-2.5 text-sm font-medium text-ink">
            {nextActionFor(incident.status)}
          </p>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <QuickStat label="Hypotheses" value={hypotheses.length} />
        <QuickStat label="Diagnosis" value={diagnosis ? "Reached" : "Not yet"} />
        <QuickStat label="Remediations" value={remediations.length} />
        <QuickStat label="Pending approvals" value={pendingApprovals} />
      </div>

      <Card>
        <CardHeader
          title="Recent activity"
          action={
            <button onClick={onViewTimeline} className="flex items-center gap-1 text-sm font-medium text-accent hover:text-accent-hover">
              Full timeline
              <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          }
        />
        <div className="px-5 py-4">
          {!recentTimeline || recentTimeline.length === 0 ? (
            <EmptyState title="No activity yet" message="Timeline events will appear here as the incident progresses." />
          ) : (
            <ul className="space-y-3">
              {[...recentTimeline]
                .sort((a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime())
                .slice(0, 4)
                .map((entry) => (
                  <li key={entry.id} className="flex items-start gap-3">
                    <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-accent" />
                    <div className="min-w-0">
                      <p className="text-sm text-ink">{entry.description}</p>
                      <p className="mt-0.5 font-mono text-xs text-ink-tertiary">{formatDateTime(entry.occurred_at)}</p>
                    </div>
                  </li>
                ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}

function QuickStat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="px-4 py-3.5">
      <p className="text-xs text-ink-tertiary">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-ink">{value}</p>
    </Card>
  );
}
