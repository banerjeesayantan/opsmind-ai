"use client";

import { FormEvent, useState } from "react";
import type { DiagnosisResponse, HypothesisResponse } from "@/lib/types";
import { formatConfidence, formatDateTime } from "@/lib/format";
import { incidentsApi } from "@/lib/incidents-api";
import { ApiError } from "@/lib/api-client";
import { Button, Card, CardHeader, EmptyState, ErrorBanner, Input, Label } from "@/components/ui";
import { HypothesisBadge } from "@/components/badges";

function defaultWindow() {
  const end = new Date();
  const start = new Date(end.getTime() - 15 * 60 * 1000);
  // datetime-local wants "YYYY-MM-DDTHH:mm"
  const toLocal = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  return { start: toLocal(start), end: toLocal(end) };
}

export function InvestigationSection({
  incidentId,
  hypotheses,
  diagnosis,
  onInvestigated,
}: {
  incidentId: string;
  hypotheses: HypothesisResponse[];
  diagnosis: DiagnosisResponse | null;
  onInvestigated: () => void;
}) {
  const initial = defaultWindow();
  const [service, setService] = useState("");
  const [windowStart, setWindowStart] = useState(initial.start);
  const [windowEnd, setWindowEnd] = useState(initial.end);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const hasRun = hypotheses.length > 0 || diagnosis !== null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await incidentsApi.investigate(incidentId, {
        service,
        window_start: new Date(windowStart).toISOString(),
        window_end: new Date(windowEnd).toISOString(),
      });
      onInvestigated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The investigation failed to run. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Investigation" subtitle="Collect telemetry and generate candidate root causes" />
      <div className="px-5 py-4">
        <form onSubmit={handleSubmit} className="mb-5 flex flex-wrap items-end gap-3 rounded-md border border-border-subtle bg-surface-raised p-4">
          <div className="min-w-[140px] flex-1">
            <Label htmlFor="inv-service">Service</Label>
            <Input id="inv-service" required value={service} onChange={(e) => setService(e.target.value)} placeholder="checkout" />
          </div>
          <div>
            <Label htmlFor="inv-start">Window start</Label>
            <Input id="inv-start" type="datetime-local" required value={windowStart} onChange={(e) => setWindowStart(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="inv-end">Window end</Label>
            <Input id="inv-end" type="datetime-local" required value={windowEnd} onChange={(e) => setWindowEnd(e.target.value)} />
          </div>
          <Button type="submit" variant="primary" loading={loading}>
            {hasRun ? "Run again" : "Run investigation"}
          </Button>
        </form>
        {error && (
          <div className="mb-4">
            <ErrorBanner message={error} />
          </div>
        )}

        {!hasRun && (
          <EmptyState title="No investigation run yet" message="Pick a service and time window above to collect evidence and generate hypotheses." />
        )}

        {hypotheses.length > 0 && (
          <div className="mb-5">
            <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-tertiary">Hypotheses</h4>
            <div className="space-y-2.5">
              {[...hypotheses]
                .sort((a, b) => b.confidence - a.confidence)
                .map((h) => (
                  <div key={h.id} className="rounded-md border border-border-subtle bg-surface-raised px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm text-ink">{h.statement}</p>
                      <span className="flex-shrink-0 font-mono text-xs text-ink-tertiary">{formatConfidence(h.confidence)}</span>
                    </div>
                    {h.reasoning && <p className="mt-1.5 text-sm text-ink-tertiary">{h.reasoning}</p>}
                    <div className="mt-2">
                      <HypothesisBadge status={h.status} />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {diagnosis && (
          <div>
            <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-tertiary">Diagnosis</h4>
            <div className="rounded-md border border-accent/30 bg-accent-muted px-4 py-3.5">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-ink">{diagnosis.probable_cause}</p>
                <span className="flex-shrink-0 font-mono text-xs text-ink-secondary">{formatConfidence(diagnosis.confidence)} confidence</span>
              </div>
              <p className="mt-1.5 text-sm text-ink-secondary">{diagnosis.impact}</p>
              <p className="mt-2 font-mono text-xs text-ink-tertiary">Diagnosed {formatDateTime(diagnosis.diagnosed_at)}</p>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
