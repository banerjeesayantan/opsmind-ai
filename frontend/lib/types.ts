/**
 * TypeScript types mirroring the FastAPI backend's actual request/response
 * schemas 1:1 - see app/schemas/auth.py and app/schemas/incident.py, and
 * the enum values in app/models/incident_enums.py, in the backend repo.
 * No field here is invented; anything not returned by the API is not
 * represented as if it were.
 */

// --- Enums (app/models/incident_enums.py) -----------------------------------

export type IncidentStatus =
  | "new"
  | "investigating"
  | "diagnosed"
  | "awaiting_approval"
  | "remediating"
  | "verifying"
  | "resolved"
  | "unresolved";

export type Severity = "low" | "medium" | "high" | "critical";

export type EvidenceSource = "log" | "metric" | "deployment_event" | "runbook";

export type HypothesisStatus = "proposed" | "validated" | "rejected";

export type RemediationActionType =
  | "rollback_deployment"
  | "restart_service"
  | "scale_service"
  | "switch_feature_flag";

export type RiskLevel = "low" | "medium" | "high";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "not_required";

export type ExecutionStatus = "pending" | "succeeded" | "failed" | "simulated";

// --- Auth (app/schemas/auth.py) ---------------------------------------------

export interface Token {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export interface UserResponse {
  id: number;
  email: string;
  token: Token;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
}

// --- Incidents (app/schemas/incident.py) ------------------------------------

export interface IncidentCreateRequest {
  title: string;
  description?: string;
  severity?: Severity;
  service: string;
}

export interface IncidentResponse {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface InvestigateRequest {
  service: string;
  window_start: string;
  window_end: string;
}

export interface InvestigateResponse {
  incident_id: string;
  status: IncidentStatus;
  evidence_count: number;
  hypothesis_count: number;
  diagnosis_id: number | null;
  probable_cause: string | null;
  confidence: number | null;
  remediation_id: number | null;
  risk_level: RiskLevel | null;
}

export interface EvidenceResponse {
  id: number;
  source: EvidenceSource;
  source_reference: string | null;
  content: string;
  raw_data: Record<string, unknown> | null;
  occurred_at: string;
  collected_at: string;
}

export interface HypothesisResponse {
  id: number;
  statement: string;
  reasoning: string | null;
  confidence: number;
  status: HypothesisStatus;
  supporting_evidence_ids: number[];
}

export interface DiagnosisResponse {
  id: number;
  hypothesis_id: number;
  probable_cause: string;
  confidence: number;
  impact: string;
  diagnosed_at: string;
}

export interface RemediationResponse {
  id: number;
  diagnosis_id: number;
  action_type: RemediationActionType;
  parameters: Record<string, unknown>;
  risk_level: RiskLevel;
  rationale: string;
  is_selected: boolean;
  recommended_at: string;
}

export interface ApprovalResponse {
  id: number;
  remediation_id: number;
  status: ApprovalStatus;
  requested_at: string;
  decided_at: string | null;
  decided_by: number | null;
  reason: string | null;
}

export interface ActionExecutionResponse {
  id: number;
  remediation_id: number;
  status: ExecutionStatus;
  executed_at: string;
  result: Record<string, unknown> | null;
  error_message: string | null;
}

export interface VerificationResponse {
  id: number;
  action_execution_id: number;
  checked_at: string;
  recovered: boolean | null;
  notes: string | null;
}

export interface IncidentResultsResponse {
  incident: IncidentResponse;
  hypotheses: HypothesisResponse[];
  diagnosis: DiagnosisResponse | null;
  remediations: RemediationResponse[];
  approvals: ApprovalResponse[];
  action_executions: ActionExecutionResponse[];
  verifications: VerificationResponse[];
}

export interface TimelineEntryResponse {
  id: number;
  event_type: string;
  description: string;
  occurred_at: string;
  event_metadata: Record<string, unknown> | null;
}

export interface RemediationCreateRequest {
  diagnosis_id: number;
  action_type: RemediationActionType;
  parameters?: Record<string, unknown>;
  rationale?: string;
  environment?: string;
}

export interface ApprovalDecisionRequest {
  approved: boolean;
  reason?: string;
}

export interface VerifyRequest {
  after_window_start?: string;
  after_window_end?: string;
}

// --- API error shape (app/main.py's validation_exception_handler, and
// plain HTTPException({"detail": "..."})) -----------------------------------

export interface ApiErrorBody {
  detail?: string;
  errors?: { field: string; message: string }[];
}
