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

// Required parameter keys per action. Mirrors the parameter models the backend's own planner enforces
// (_RollbackParams, _RestartParams, _ScaleParams, _FeatureFlagParams in
// app/investigation/nodes/remediation_planner.py). The manual-recommend endpoint itself accepts anything
// (e.g. a rollback with no deployment_id returns 201), so without this a typo creates a remediation that
// can't actually run.
const REQUIRED_PARAMS: Record<RemediationActionType, string[]> = {
  rollback_deployment: ["deployment_id"],
  restart_service: ["service"],
  scale_service: ["service", "target_replicas", "direction"],
  switch_feature_flag: ["flag_name", "enabled"],
};

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
      const parsed: unknown = parametersText.trim() ? JSON.parse(parametersText) : {};
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("not an object");
      parameters = parsed as Record<string, unknown>;
    } catch {
      setError('Parameters must be a JSON object, e.g. {"service": "checkout"}');
      return;
    }
    const missing = REQUIRED_PARAMS[actionType].filter((key) => parameters[key] === undefined || parameters[key] === "");
    if (missing.length > 0) {
      setError(`${ACTION_TYPES.find((a) => a.value === actionType)?.label ?? actionType} needs parameters: ${missing.join(", ")}`);
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
        <Label htmlFor="parameters">Parameters (JSON) &mdash; required: {REQUIRED_PARAMS[actionType].join(", ")}</Label>
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
