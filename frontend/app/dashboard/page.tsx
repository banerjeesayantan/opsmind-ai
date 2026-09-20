"use client";

import Link from "next/link";
import { Activity, CheckCircle2, Clock, Flame, Search } from "lucide-react";
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

function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  tone?: "default" | "warning" | "critical";
}) {
  const toneStyles: Record<string, { text: string; iconBg: string; iconText: string }> = {
    default: { text: "text-ink", iconBg: "bg-surface-raised", iconText: "text-ink-secondary" },
    warning: { text: "text-severity-high", iconBg: "bg-severity-high/10", iconText: "text-severity-high" },
    critical: { text: "text-severity-critical", iconBg: "bg-severity-critical/10", iconText: "text-severity-critical" },
  };
  const s = toneStyles[tone] ?? toneStyles.default!;
  return (
    <Card className="px-5 py-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-tertiary">{label}</p>
        <div className={`flex h-7 w-7 items-center justify-center rounded-md ${s.iconBg}`}>
          <Icon className={`h-3.5 w-3.5 ${s.iconText}`} strokeWidth={2} />
        </div>
      </div>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${s.text}`}>{value}</p>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: incidents, error, loading, reload } = useAsync(() => incidentsApi.list(), []);

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-5 py-6 sm:px-8 sm:py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
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
                <Skeleton key={i} className="h-[80px]" />
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
  const investigating = incidents.filter((i) => i.status === "investigating");
  const awaitingApproval = incidents.filter((i) => i.status === "awaiting_approval");
  const critical = incidents.filter((i) => i.severity === "critical" && OPEN_STATUSES.includes(i.status));

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
        <StatCard label="Open incidents" value={open.length} icon={Activity} />
        <StatCard label="Critical & open" value={critical.length} icon={Flame} tone={critical.length > 0 ? "critical" : "default"} />
        <StatCard label="Investigating" value={investigating.length} icon={Search} />
        <StatCard
          label="Awaiting approval"
          value={awaitingApproval.length}
          icon={Clock}
          tone={awaitingApproval.length > 0 ? "warning" : "default"}
        />
      </div>

      <Card>
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Needs your approval</h2>
            <p className="mt-0.5 text-sm text-ink-tertiary">Remediations blocked on a human decision</p>
          </div>
        </div>
        {awaitingApproval.length === 0 ? (
          <div className="flex items-center gap-2.5 px-5 py-6">
            <CheckCircle2 className="h-4 w-4 text-severity-low" strokeWidth={2} aria-hidden="true" />
            <p className="text-sm text-ink-tertiary">Nothing is waiting on you right now.</p>
          </div>
        ) : (
          awaitingApproval.map((incident) => <IncidentRow key={incident.id} incident={incident} />)
        )}
      </Card>

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
