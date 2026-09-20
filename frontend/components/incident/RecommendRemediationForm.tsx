"use client";

import { FormEvent, useState } from "react";
import type { RemediationActionType } from "@/lib/types";
import { incidentsApi } from "@/lib/incidents-api";
import { ApiError } from "@/lib/api-client";
import { Button, ErrorBanner, Input, Label, Select, Textarea } from "@/components/ui";

const ACTION_TYPES: { value: RemediationActionType; label: string }[] = [
  { value: "rollback_deployment", label: "Roll back deployment" },
  { value: "restart_service", label: "Restart service" },
  { value: "scale_service", label: "Scale service" },
  { value: "switch_feature_flag", label: "Switch feature flag" },
];

export function RecommendRemediationForm({
  incidentId,
  diagnosisId,
  onRecommended,
}: {
  incidentId: string;
  diagnosisId: number;
  onRecommended: () => void;
}) {
  const [actionType, setActionType] = useState<RemediationActionType>("restart_service");
  const [environment, setEnvironment] = useState("production");
  const [rationale, setRationale] = useState("");
  const [parametersText, setParametersText] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    let parameters: Record<string, unknown>;
    try {
      parameters = parametersText.trim() ? JSON.parse(parametersText) : {};
    } catch {
      setError("Parameters must be valid JSON, e.g. {}");
      return;
    }

    setLoading(true);
    try {
      await incidentsApi.recommendRemediation(incidentId, {
        diagnosis_id: diagnosisId,
        action_type: actionType,
        parameters,
        rationale,
        environment,
      });
      onRecommended();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't recommend a remediation. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-md border border-border-subtle bg-surface-raised p-4">
      {error && <ErrorBanner message={error} />}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="action-type">Action</Label>
          <Select id="action-type" value={actionType} onChange={(e) => setActionType(e.target.value as RemediationActionType)}>
            {ACTION_TYPES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="environment">Environment</Label>
          <Input id="environment" value={environment} onChange={(e) => setEnvironment(e.target.value)} placeholder="production" />
        </div>
      </div>
      <div>
        <Label htmlFor="rationale">Rationale</Label>
        <Textarea
          id="rationale"
          rows={2}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Why this action addresses the diagnosis"
        />
      </div>
      <div>
        <Label htmlFor="parameters">Parameters (JSON)</Label>
        <Textarea
          id="parameters"
          rows={2}
          value={parametersText}
          onChange={(e) => setParametersText(e.target.value)}
          className="font-mono"
          placeholder="{}"
        />
      </div>
      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={loading}>
          Recommend remediation
        </Button>
      </div>
    </form>
  );
}
