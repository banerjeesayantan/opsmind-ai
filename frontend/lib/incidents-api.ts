import { api } from "./api-client";
import type {
  ApprovalDecisionRequest,
  ApprovalResponse,
  ActionExecutionResponse,
  EvidenceResponse,
  IncidentCreateRequest,
  IncidentResponse,
  IncidentResultsResponse,
  InvestigateRequest,
  InvestigateResponse,
  RemediationCreateRequest,
  RemediationResponse,
  TimelineEntryResponse,
  VerificationResponse,
  VerifyRequest,
} from "./types";

// Every function here maps 1:1 to a route in app/api/v1/incidents.py -
// same path, method, request body and response shape.

export const incidentsApi = {
  create: (body: IncidentCreateRequest) => api.post<IncidentResponse>("/incidents", body),

  list: () => api.get<IncidentResponse[]>("/incidents"),

  getResults: (incidentId: string) => api.get<IncidentResultsResponse>(`/incidents/${incidentId}`),

  getTimeline: (incidentId: string) => api.get<TimelineEntryResponse[]>(`/incidents/${incidentId}/timeline`),

  getEvidence: (incidentId: string) => api.get<EvidenceResponse[]>(`/incidents/${incidentId}/evidence`),

  investigate: (incidentId: string, body: InvestigateRequest) =>
    api.post<InvestigateResponse>(`/incidents/${incidentId}/investigate`, body),

  recommendRemediation: (incidentId: string, body: RemediationCreateRequest) =>
    api.post<RemediationResponse>(`/incidents/${incidentId}/remediations`, body),

  listApprovals: (incidentId: string) => api.get<ApprovalResponse[]>(`/incidents/${incidentId}/approvals`),

  decideApproval: (incidentId: string, approvalId: number, body: ApprovalDecisionRequest) =>
    api.post<ApprovalResponse>(`/incidents/${incidentId}/approvals/${approvalId}/decision`, body),

  executeRemediation: (incidentId: string, remediationId: number) =>
    api.post<ActionExecutionResponse>(`/incidents/${incidentId}/remediations/${remediationId}/execute`),

  verifyExecution: (incidentId: string, executionId: number, body: VerifyRequest) =>
    api.post<VerificationResponse>(`/incidents/${incidentId}/executions/${executionId}/verify`, body),
};
