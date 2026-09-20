"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button, Card, EmptyState, ErrorBanner, PageLoading, Skeleton } from "@/components/ui";
import { IncidentRow } from "@/components/IncidentRow";
import { incidentsApi } from "@/lib/incidents-api";
import { useAsync } from "@/lib/use-async";
import type { IncidentResponse } from "@/lib/types";

const OPEN_STATUSES: IncidentResponse["status"][] = [
  "new",
  "investigating",
  "diagnosed",
  "awaiting_approval",
  "remediating",
  "verifying",
];

function StatCard({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "warning" | "critical" }) {
  const toneClass = tone === "warning" ? "text-severity-high" : tone === "critical" ? "text-severity-critical" : "text-ink";
  return (
    <Card className="px-5 py-4">
      <p className="text-sm text-ink-tertiary">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</p>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: incidents, error, loading, reload } = useAsync(() => incidentsApi.list(), []);

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-8 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-ink">Dashboard</h1>
            <p className="mt-1 text-sm text-ink-tertiary">Your team&apos;s incident activity at a glance</p>
          </div>
          <Link href="/incidents?new=1">
            <Button variant="primary">New incident</Button>
          </Link>
        </div>

        {loading && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-[76px]" />
              ))}
            </div>
            <PageLoading label="Loading your incidents" />
          </div>
        )}

        {!loading && error && <ErrorBanner message={error} onRetry={reload} />}

        {!loading && !error && incidents && <DashboardContent incidents={incidents} />}
      </div>
    </AppShell>
  );
}

function DashboardContent({ incidents }: { incidents: IncidentResponse[] }) {
  const open = incidents.filter((i) => OPEN_STATUSES.includes(i.status));
  const awaitingApproval = incidents.filter((i) => i.status === "awaiting_approval");
  const critical = incidents.filter((i) => i.severity === "critical" && OPEN_STATUSES.includes(i.status));
  const resolved = incidents.filter((i) => i.status === "resolved");

  const recent = [...incidents]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 6);

  if (incidents.length === 0) {
    return (
      <EmptyState
        title="No incidents yet"
        message="When something breaks, open an incident here to start an AI-assisted investigation."
        action={
          <Link href="/incidents?new=1">
            <Button variant="primary">Create your first incident</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Open incidents" value={open.length} />
        <StatCard label="Awaiting your approval" value={awaitingApproval.length} tone={awaitingApproval.length > 0 ? "warning" : "default"} />
        <StatCard label="Critical & open" value={critical.length} tone={critical.length > 0 ? "critical" : "default"} />
        <StatCard label="Resolved" value={resolved.length} />
      </div>

      {awaitingApproval.length > 0 && (
        <Card>
          <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">Needs your approval</h2>
              <p className="mt-0.5 text-sm text-ink-tertiary">Remediations blocked on a human decision</p>
            </div>
          </div>
          {awaitingApproval.map((incident) => (
            <IncidentRow key={incident.id} incident={incident} />
          ))}
        </Card>
      )}

      <Card>
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <h2 className="text-sm font-semibold text-ink">Recent incidents</h2>
          <Link href="/incidents" className="text-sm font-medium text-accent hover:text-accent-hover">
            View all
          </Link>
        </div>
        {recent.map((incident) => (
          <IncidentRow key={incident.id} incident={incident} />
        ))}
      </Card>
    </div>
  );
}
