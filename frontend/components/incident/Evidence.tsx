import type { EvidenceResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Card, CardHeader, EmptyState, ErrorBanner, Skeleton } from "@/components/ui";

const SOURCE_LABEL: Record<EvidenceResponse["source"], string> = {
  log: "Log",
  metric: "Metric",
  deployment_event: "Deployment",
  runbook: "Runbook",
};

export function EvidenceSection({
  evidence,
  loading,
  error,
}: {
  evidence: EvidenceResponse[] | null;
  loading: boolean;
  error: string | null;
}) {
  return (
    <Card>
      <CardHeader title="Evidence" subtitle="Raw telemetry collected during investigation" />
      <div className="px-5 py-4">
        {loading && (
          <div className="space-y-3">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        )}
        {!loading && error && <ErrorBanner message={error} />}
        {!loading && !error && evidence && evidence.length === 0 && (
          <EmptyState title="No evidence collected yet" message="Run an investigation to gather logs, metrics, and deployment events." />
        )}
        {!loading && !error && evidence && evidence.length > 0 && (
          <div className="space-y-3">
            {evidence.map((item) => (
              <div key={item.id} className="rounded-md border border-border-subtle bg-surface-raised px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="rounded bg-surface px-1.5 py-0.5 font-mono text-[11px] font-medium text-ink-secondary">
                    {SOURCE_LABEL[item.source]}
                  </span>
                  <span className="font-mono text-xs text-ink-tertiary">{formatDateTime(item.occurred_at)}</span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-ink-secondary">{item.content}</p>
                {item.source_reference && <p className="mt-1.5 font-mono text-xs text-ink-tertiary">{item.source_reference}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
