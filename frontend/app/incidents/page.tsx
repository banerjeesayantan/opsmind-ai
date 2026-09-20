"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus, Search, X } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Button, Card, EmptyState, ErrorBanner, Select, Skeleton } from "@/components/ui";
import { IncidentRow } from "@/components/IncidentRow";
import { CreateIncidentModal } from "@/components/CreateIncidentModal";
import { incidentsApi } from "@/lib/incidents-api";
import { useAsync } from "@/lib/use-async";
import type { IncidentStatus, Severity } from "@/lib/types";
import { statusLabel } from "@/lib/format";

const STATUS_FILTERS: IncidentStatus[] = [
  "new",
  "investigating",
  "diagnosed",
  "awaiting_approval",
  "remediating",
  "verifying",
  "resolved",
  "unresolved",
];

function IncidentListSkeleton() {
  return (
    <Card>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 border-b border-border-subtle px-5 py-3.5 last:border-b-0">
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-3.5 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-5 w-16 flex-shrink-0" />
          <Skeleton className="hidden h-5 w-24 flex-shrink-0 sm:block" />
        </div>
      ))}
    </Card>
  );
}

function IncidentsListContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [modalOpen, setModalOpen] = useState(params.get("new") === "1");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");

  const { data: incidents, error, loading, reload } = useAsync(() => incidentsApi.list(), []);

  const hasActiveFilters = search.trim() !== "" || statusFilter !== "all" || severityFilter !== "all";

  const filtered = useMemo(() => {
    if (!incidents) return [];
    const query = search.trim().toLowerCase();
    return incidents
      .filter((i) => statusFilter === "all" || i.status === statusFilter)
      .filter((i) => severityFilter === "all" || i.severity === severityFilter)
      .filter((i) => query === "" || i.title.toLowerCase().includes(query) || i.id.toLowerCase().includes(query))
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [incidents, statusFilter, severityFilter, search]);

  function clearFilters() {
    setSearch("");
    setStatusFilter("all");
    setSeverityFilter("all");
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-5 py-6 sm:px-8 sm:py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-ink">Incidents</h1>
            <p className="mt-1 text-sm text-ink-tertiary">Every incident your team has opened</p>
          </div>
          <Button variant="primary" onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" strokeWidth={2.25} aria-hidden="true" />
            New incident
          </Button>
        </div>

        {incidents && incidents.length > 0 && (
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1 sm:max-w-xs">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-tertiary"
                strokeWidth={2}
                aria-hidden="true"
              />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by title or ID"
                aria-label="Search incidents by title or ID"
                className="w-full rounded-md border border-border bg-surface-raised py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-tertiary transition-colors focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
            <div className="flex gap-3">
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | "all")}
                aria-label="Filter by status"
                className="w-full sm:w-48"
              >
                <option value="all">All statuses</option>
                {STATUS_FILTERS.map((s) => (
                  <option key={s} value={s}>
                    {statusLabel(s)}
                  </option>
                ))}
              </Select>
              <Select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")}
                aria-label="Filter by severity"
                className="w-full sm:w-40"
              >
                <option value="all">All severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </Select>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={clearFilters} className="flex-shrink-0">
                  <X className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
                  Clear
                </Button>
              )}
            </div>
          </div>
        )}

        {loading && <IncidentListSkeleton />}
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
          <EmptyState
            title="No incidents match these filters"
            message="Try a different search term, status, or severity."
            action={
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            }
          />
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
