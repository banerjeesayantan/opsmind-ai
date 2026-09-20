"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ErrorBanner, PageLoading } from "@/components/ui";
import { IncidentHeader } from "@/components/incident/Header";
import { ResolutionBanner } from "@/components/incident/ResolutionBanner";
import { InvestigationSection } from "@/components/incident/Investigation";
import { EvidenceSection } from "@/components/incident/Evidence";
import { RemediationSection } from "@/components/incident/RemediationPipeline";
import { TimelineSection } from "@/components/incident/Timeline";
import { incidentsApi } from "@/lib/incidents-api";
import { useAsync } from "@/lib/use-async";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;

  const results = useAsync(() => incidentsApi.getResults(incidentId), [incidentId]);
  const timeline = useAsync(() => incidentsApi.getTimeline(incidentId), [incidentId]);
  const evidence = useAsync(() => incidentsApi.getEvidence(incidentId), [incidentId]);

  const reloadAll = useCallback(() => {
    results.reload();
    timeline.reload();
    evidence.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  return (
    <AppShell>
      {results.loading && (
        <div className="flex min-h-[60vh] items-center justify-center">
          <PageLoading label="Loading incident" />
        </div>
      )}

      {!results.loading && results.error && (
        <div className="mx-auto max-w-3xl px-8 py-8">
          <ErrorBanner title="Couldn't load this incident" message={results.error} onRetry={results.reload} />
        </div>
      )}

      {!results.loading && !results.error && results.data && (
        <>
          <IncidentHeader incident={results.data.incident} />
          <div className="mx-auto max-w-3xl space-y-5 px-8 py-6">
            <ResolutionBanner status={results.data.incident.status} />

            <InvestigationSection
              incidentId={incidentId}
              hypotheses={results.data.hypotheses}
              diagnosis={results.data.diagnosis}
              onInvestigated={reloadAll}
            />

            <EvidenceSection evidence={evidence.data} loading={evidence.loading} error={evidence.error} />

            <RemediationSection
              incidentId={incidentId}
              diagnosis={results.data.diagnosis}
              remediations={results.data.remediations}
              approvals={results.data.approvals}
              executions={results.data.action_executions}
              verifications={results.data.verifications}
              onChanged={reloadAll}
            />

            <TimelineSection entries={timeline.data} loading={timeline.loading} error={timeline.error} />
          </div>
        </>
      )}
    </AppShell>
  );
}
