"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Button, Card, EmptyState, ErrorBanner, PageLoading, Select } from "@/components/ui";
import { IncidentRow } from "@/components/IncidentRow";
import { CreateIncidentModal } from "@/components/CreateIncidentModal";
import { incidentsApi } from "@/lib/incidents-api";
import { useAsync } from "@/lib/use-async";
import type { IncidentStatus, Severity } from "@/lib/types";
import { statusLabel } from "@/lib/format";

const STATUS_FILTERS: (IncidentStatus | "all")[] = [
  "all",
  "new",
  "investigating",
  "diagnosed",
  "awaiting_approval",
  "remediating",
  "verifying",
  "resolved",
  "unresolved",
];

function IncidentsListContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [modalOpen, setModalOpen] = useState(params.get("new") === "1");
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");

  const { data: incidents, error, loading, reload } = useAsync(() => incidentsApi.list(), []);

  const filtered = useMemo(() => {
    if (!incidents) return [];
    return incidents
      .filter((i) => statusFilter === "all" || i.status === statusFilter)
      .filter((i) => severityFilter === "all" || i.severity === severityFilter)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [incidents, statusFilter, severityFilter]);

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-8 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-ink">Incidents</h1>
            <p className="mt-1 text-sm text-ink-tertiary">Every incident your team has opened</p>
          </div>
          <Button variant="primary" onClick={() => setModalOpen(true)}>
            New incident
          </Button>
        </div>

        {incidents && incidents.length > 0 && (
          <div className="mb-4 flex gap-3">
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | "all")} className="w-48">
              <option value="all">All statuses</option>
              {STATUS_FILTERS.filter((s) => s !== "all").map((s) => (
                <option key={s} value={s}>
                  {statusLabel(s)}
                </option>
              ))}
            </Select>
            <Select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")} className="w-40">
              <option value="all">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </Select>
          </div>
        )}

        {loading && <PageLoading label="Loading incidents" />}
        {!loading && error && <ErrorBanner message={error} onRetry={reload} />}

        {!loading && !error && incidents && incidents.length === 0 && (
          <EmptyState
            title="No incidents yet"
            message="When something breaks, open an incident here to start an AI-assisted investigation."
            action={
              <Button variant="primary" onClick={() => setModalOpen(true)}>
                Create your first incident
              </Button>
            }
          />
        )}

        {!loading && !error && incidents && incidents.length > 0 && filtered.length === 0 && (
          <EmptyState title="No incidents match these filters" message="Try a different status or severity." />
        )}

        {!loading && !error && filtered.length > 0 && (
          <Card>
            {filtered.map((incident) => (
              <IncidentRow key={incident.id} incident={incident} />
            ))}
          </Card>
        )}
      </div>

      {modalOpen && (
        <CreateIncidentModal
          onClose={() => setModalOpen(false)}
          onCreated={(incident) => {
            setModalOpen(false);
            router.push(`/incidents/${incident.id}`);
          }}
        />
      )}
    </AppShell>
  );
}

export default function IncidentsPage() {
  return (
    <Suspense fallback={null}>
      <IncidentsListContent />
    </Suspense>
  );
}
