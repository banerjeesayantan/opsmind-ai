"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { FileText, History, LayoutGrid, Search, Wrench } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { ErrorBanner, PageLoading } from "@/components/ui";
import { Tabs, TabPanel, type TabItem } from "@/components/Tabs";
import { IncidentHeader } from "@/components/incident/Header";
import { ResolutionBanner } from "@/components/incident/ResolutionBanner";
import { OverviewTab } from "@/components/incident/Overview";
import { InvestigationSection } from "@/components/incident/Investigation";
import { EvidenceSection } from "@/components/incident/Evidence";
import { RemediationSection } from "@/components/incident/RemediationPipeline";
import { TimelineSection } from "@/components/incident/Timeline";
import { incidentsApi } from "@/lib/incidents-api";
import { useAsync } from "@/lib/use-async";

type TabKey = "overview" | "investigation" | "evidence" | "remediation" | "timeline";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const results = useAsync(() => incidentsApi.getResults(incidentId), [incidentId]);
  const timeline = useAsync(() => incidentsApi.getTimeline(incidentId), [incidentId]);
  const evidence = useAsync(() => incidentsApi.getEvidence(incidentId), [incidentId]);

  const reloadAll = useCallback(() => {
    results.reload();
    timeline.reload();
    evidence.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  const tabs: TabItem[] = [
    { key: "overview", label: "Overview", icon: LayoutGrid },
    { key: "investigation", label: "Investigation", icon: Search, count: results.data?.hypotheses.length },
    { key: "evidence", label: "Evidence", icon: FileText, count: evidence.data?.length },
    { key: "remediation", label: "Remediation", icon: Wrench, count: results.data?.remediations.length },
    { key: "timeline", label: "Timeline", icon: History, count: timeline.data?.length },
  ];

  return (
    <AppShell>
      {results.loading && (
        <div className="flex min-h-[60vh] items-center justify-center">
          <PageLoading label="Loading incident" />
        </div>
      )}

      {!results.loading && results.error && (
        <div className="mx-auto max-w-3xl px-5 py-8 sm:px-8">
          <ErrorBanner title="Couldn't load this incident" message={results.error} onRetry={results.reload} />
        </div>
      )}

      {!results.loading && !results.error && results.data && (
        <>
          <IncidentHeader incident={results.data.incident} />

          <div className="border-b border-border bg-surface px-5 sm:px-8">
            <div className="mx-auto max-w-3xl">
              <Tabs items={tabs} active={activeTab} onChange={(key) => setActiveTab(key as TabKey)} />
            </div>
          </div>

          <div className="mx-auto max-w-3xl space-y-5 px-5 py-6 sm:px-8">
            <ResolutionBanner status={results.data.incident.status} />

            <TabPanel tabKey="overview" active={activeTab}>
              <OverviewTab results={results.data} recentTimeline={timeline.data} onViewTimeline={() => setActiveTab("timeline")} />
            </TabPanel>

            <TabPanel tabKey="investigation" active={activeTab}>
              <InvestigationSection
                incidentId={incidentId}
                hypotheses={results.data.hypotheses}
                diagnosis={results.data.diagnosis}
                onInvestigated={reloadAll}
              />
            </TabPanel>

            <TabPanel tabKey="evidence" active={activeTab}>
              <EvidenceSection evidence={evidence.data} loading={evidence.loading} error={evidence.error} />
            </TabPanel>

            <TabPanel tabKey="remediation" active={activeTab}>
              <RemediationSection
                incidentId={incidentId}
                diagnosis={results.data.diagnosis}
                remediations={results.data.remediations}
                approvals={results.data.approvals}
                executions={results.data.action_executions}
                verifications={results.data.verifications}
                onChanged={reloadAll}
              />
            </TabPanel>

            <TabPanel tabKey="timeline" active={activeTab}>
              <TimelineSection entries={timeline.data} loading={timeline.loading} error={timeline.error} />
            </TabPanel>
          </div>
        </>
      )}
    </AppShell>
  );
}
