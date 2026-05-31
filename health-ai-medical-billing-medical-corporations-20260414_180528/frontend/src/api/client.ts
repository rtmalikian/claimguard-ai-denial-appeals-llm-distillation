import axios from 'axios';

const AUTH_TOKEN_KEY = 'claimguard.auth.token';
const AUTH_USER_KEY = 'claimguard.auth.user';
const AUTH_EXPIRES_AT_KEY = 'claimguard.auth.expires_at';
const AUTH_LAST_ACTIVITY_AT_KEY = 'claimguard.auth.last_activity_at';
const AUTH_IDLE_TIMEOUT_SECONDS_KEY = 'claimguard.auth.idle_timeout_seconds';
export const DEFAULT_SESSION_TIMEOUT_SECONDS = 30 * 60;
export const SESSION_TIMEOUT_CHECK_INTERVAL_MS = 30 * 1000;

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  maxRedirects: 5,
  validateStatus: (status) => status >= 200 && status < 400,
});

export interface AuthUser {
  id: number;
  email: string;
  full_name?: string | null;
  role: 'admin' | 'billing_staff' | 'viewer';
  is_active: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface PatientResponse {
  id: number;
  mrn: string;
  first_name?: string | null;
  last_name?: string | null;
  date_of_birth?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface PatientPayload {
  mrn: string;
  first_name?: string | null;
  last_name?: string | null;
  date_of_birth?: string | null;
}

export interface PatientSearchParams {
  skip?: number;
  limit?: number;
  first_name?: string;
  last_name?: string;
  dob?: string;
}

const getSessionStorage = () => {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage;
};

const parseStoredNumber = (value: string | null): number | null => {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const redirectToLogin = () => {
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.assign('/login');
  }
};

export const clearAuthSession = () => {
  const storage = getSessionStorage();
  if (!storage) return;
  storage.removeItem(AUTH_TOKEN_KEY);
  storage.removeItem(AUTH_USER_KEY);
  storage.removeItem(AUTH_EXPIRES_AT_KEY);
  storage.removeItem(AUTH_LAST_ACTIVITY_AT_KEY);
  storage.removeItem(AUTH_IDLE_TIMEOUT_SECONDS_KEY);
};

export interface AuthSessionTiming {
  expiresAt: number;
  lastActivityAt: number;
  idleTimeoutSeconds: number;
}

export const getAuthSessionTiming = (): AuthSessionTiming | null => {
  const storage = getSessionStorage();
  if (!storage?.getItem(AUTH_TOKEN_KEY)) return null;

  const expiresAt = parseStoredNumber(storage.getItem(AUTH_EXPIRES_AT_KEY));
  const lastActivityAt = parseStoredNumber(storage.getItem(AUTH_LAST_ACTIVITY_AT_KEY));
  const idleTimeoutSeconds = parseStoredNumber(storage.getItem(AUTH_IDLE_TIMEOUT_SECONDS_KEY));

  if (!expiresAt || !lastActivityAt || !idleTimeoutSeconds) return null;
  return { expiresAt, lastActivityAt, idleTimeoutSeconds };
};

export const isAuthSessionExpired = (now = Date.now()) => {
  const storage = getSessionStorage();
  if (!storage?.getItem(AUTH_TOKEN_KEY)) return false;

  const timing = getAuthSessionTiming();
  if (!timing) return true;

  const idleTimeoutMs = timing.idleTimeoutSeconds * 1000;
  return now >= timing.expiresAt || now - timing.lastActivityAt >= idleTimeoutMs;
};

export const markAuthActivity = (now = Date.now()) => {
  const storage = getSessionStorage();
  if (!storage?.getItem(AUTH_TOKEN_KEY) || isAuthSessionExpired(now)) return false;

  storage.setItem(AUTH_LAST_ACTIVITY_AT_KEY, String(now));
  return true;
};

export const enforceAuthSessionTimeout = () => {
  if (!isAuthSessionExpired()) return false;
  clearAuthSession();
  redirectToLogin();
  return true;
};

export const getStoredToken = () => {
  const storage = getSessionStorage();
  const token = storage?.getItem(AUTH_TOKEN_KEY) || null;
  if (!token) return null;

  if (isAuthSessionExpired()) {
    clearAuthSession();
    return null;
  }

  return token;
};

export const getStoredUser = (): AuthUser | null => {
  const storage = getSessionStorage();
  const rawUser = storage?.getItem(AUTH_USER_KEY);
  if (!rawUser) return null;
  if (!storage?.getItem(AUTH_TOKEN_KEY) || isAuthSessionExpired()) {
    clearAuthSession();
    return null;
  }

  try {
    return JSON.parse(rawUser) as AuthUser;
  } catch {
    clearAuthSession();
    return null;
  }
};

export const setAuthSession = (
  token: string,
  user: AuthUser,
  expiresInSeconds = DEFAULT_SESSION_TIMEOUT_SECONDS,
) => {
  const storage = getSessionStorage();
  if (!storage) return;
  const safeExpiresInSeconds =
    Number.isFinite(expiresInSeconds) && expiresInSeconds > 0
      ? expiresInSeconds
      : DEFAULT_SESSION_TIMEOUT_SECONDS;
  const idleTimeoutSeconds = Math.min(safeExpiresInSeconds, DEFAULT_SESSION_TIMEOUT_SECONDS);
  const now = Date.now();
  storage.setItem(AUTH_TOKEN_KEY, token);
  storage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  storage.setItem(AUTH_EXPIRES_AT_KEY, String(now + safeExpiresInSeconds * 1000));
  storage.setItem(AUTH_LAST_ACTIVITY_AT_KEY, String(now));
  storage.setItem(AUTH_IDLE_TIMEOUT_SECONDS_KEY, String(idleTimeoutSeconds));
};

api.interceptors.request.use((config) => {
  if (enforceAuthSessionTimeout()) {
    return Promise.reject(new Error('auth_session_expired'));
  }

  const token = getStoredToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthSession();
      redirectToLogin();
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (credentials: LoginCredentials) => api.post<LoginResponse>('/auth/login', credentials),
  me: () => api.get<AuthUser>('/auth/me'),
  logout: () => api.post('/auth/logout'),
};

const patientQueryString = (params: PatientSearchParams = {}) => {
  const query = new URLSearchParams();
  query.set('skip', String(params.skip ?? 0));
  query.set('limit', String(params.limit ?? 100));

  if (params.first_name) query.set('first_name', params.first_name);
  if (params.last_name) query.set('last_name', params.last_name);
  if (params.dob) query.set('dob', params.dob);

  return query.toString();
};

export const patientsApi = {
  create: (data: PatientPayload) => api.post<PatientResponse>('/patients/', data),
  list: (params: PatientSearchParams = {}) => api.get<PatientResponse[]>(`/patients/?${patientQueryString(params)}`),
  get: (id: number) => api.get<PatientResponse>(`/patients/${id}`),
  getByMrn: (mrn: string) => api.get<PatientResponse>(`/patients/mrn/${encodeURIComponent(mrn)}`),
  update: (id: number, data: PatientPayload) => api.put<PatientResponse>(`/patients/${id}`, data),
  delete: (id: number) => api.delete(`/patients/${id}`),
};

export interface ClaimData {
  patient_id: number;
  provider_id: number;
  claim_data: Record<string, unknown>;
  diagnosis_codes?: string[];
  procedure_codes?: string[];
}

export interface DenialReason {
  reason: string;
  severity: string;
  code?: string;
}

export interface Recommendation {
  action: string;
  description: string;
  priority: string;
}

export type HumanReviewStatus = 'not_required' | 'required';

export interface ClaimHumanReviewGate {
  human_review_required: boolean;
  human_review_status: HumanReviewStatus;
  human_review_reasons: string[];
  human_review_threshold: number;
  human_review_next_action: string;
}

export interface ClaimPredictionResponse extends ClaimHumanReviewGate {
  claim_id?: number | null;
  denial_prediction: number;
  denial_confidence: number;
  denial_reasons: DenialReason[];
  recommendations: Recommendation[];
  analyzed_at?: string;
}

export interface ClaimSubmitResponse extends ClaimHumanReviewGate {
  claim_id: number;
  status: string;
  denial_prediction: number;
  denial_confidence: number;
  denial_reasons: DenialReason[];
  recommendations: Recommendation[];
  message: string;
}

export type SourceStatus = 'known_from_documents' | 'inferred' | 'missing_needs_human_verification' | 'cited_rule';
export type ConfidenceLabel = 'low' | 'medium' | 'high';
export type ExportFormat = 'markdown' | 'docx' | 'pdf';
export type PhiStatus = 'contains_phi' | 'deidentified' | 'no_phi' | 'unknown';
export type RetrievalSourceAccessScope = 'owner' | 'billing_team' | 'admin_only';

export interface SourceReference {
  source_status: SourceStatus;
  source_document_id?: string | null;
  source_page?: string | null;
  source_excerpt_ref?: string | null;
  source_url?: string | null;
  source_title?: string | null;
  extraction_method:
    | 'ocr'
    | 'manual_entry'
    | 'api'
    | 'model_inference'
    | 'rule_lookup'
    | 'system_import';
  confidence: number;
  human_verified: boolean;
  inference_path?: string | null;
  verification_note?: string | null;
}

export interface FactItem {
  field: string;
  value?: unknown;
  source: SourceReference;
}

export interface WorkflowTask {
  task: string;
  owner: string;
  due_date?: string | null;
  source: SourceReference;
  verification_status: 'open' | 'blocked' | 'verified';
  reason?: string | null;
}

export interface CitedRule {
  rule_id: string;
  summary: string;
  citation: string;
  source: SourceReference;
}

export interface RouteEvidence {
  fact: string;
  source: SourceReference;
}

export interface RouteConsidered {
  route: string;
  decision: 'selected' | 'not_selected' | 'verify_locally';
  reason: string;
}

export interface DeadlineItem {
  deadline_type: string;
  source_stated_deadline?: string | null;
  calculated_deadline?: string | null;
  rule_source_id?: string | null;
  assumptions: string[];
  verification_status: 'needs_human_verification' | 'verified';
  source: SourceReference;
}

export interface EvidenceGap {
  evidence_type: string;
  description: string;
  owner: string;
  priority: 'low' | 'medium' | 'high';
  source: SourceReference;
  human_verification_required: boolean;
}

export interface AttachmentIndexItem {
  label: string;
  description: string;
  source_status: SourceStatus;
  required_before_submission: boolean;
}

export interface SubmissionPlan {
  route: string;
  required_channel: string;
  proof_to_capture: string[];
  blocker_tasks: string[];
  source: SourceReference;
}

export interface FollowUpItem {
  action: string;
  due_date?: string | null;
  trigger: string;
  source: SourceReference;
  human_verification_required: boolean;
}

export interface QualityCheck {
  check: string;
  status: 'pass' | 'warning' | 'blocker';
  details: string;
}

export interface PhiScanFinding {
  finding_type: string;
  line: number;
  column: number;
  category: string;
}

export interface PhiScanSummary {
  status: 'not_scanned' | 'no_findings' | 'findings_detected';
  finding_count: number;
  finding_types: string[];
  contains_phi_or_pii_like_content: boolean;
  values_redacted: boolean;
  review_required: boolean;
  note: string;
}

export interface WorkflowPhaseChecklistItem {
  phase_id: string;
  phase_name: string;
  status: 'not_started' | 'in_progress' | 'blocked' | 'ready_for_human_review';
  owner: string;
  output_artifact: string;
  human_verification_required: boolean;
  related_tasks: string[];
  source: SourceReference;
}

export interface RetrievedSourceSnippet {
  source_id: string;
  title: string;
  source_type: string;
  citation: string;
  text: string;
  jurisdiction?: string | null;
  payer_type?: string | null;
  date?: string | null;
  phi_status: string;
  license_status: string;
  score: number;
}

export interface DenialWorkflowAnalysisRequest {
  document_text: string;
  document_type?: string;
  source_document_id?: string;
  source_title?: string;
  source_url?: string | null;
  phi_status?: PhiStatus;
  retrieved_sources?: RetrievedSourceSnippet[];
  generate_draft?: boolean;
  use_llm?: boolean;
}

export interface DenialWorkflowAnalysisResponse {
  document_type: string;
  case_summary: string;
  known_from_documents: FactItem[];
  inferred: FactItem[];
  missing_needs_human_verification: WorkflowTask[];
  cited_rules: CitedRule[];
  payer_name?: string | null;
  payer_type: string;
  plan_type: string;
  denial_type: string;
  recommended_route: string;
  route_confidence: ConfidenceLabel;
  route_evidence: RouteEvidence[];
  routes_considered: RouteConsidered[];
  deadline_table: DeadlineItem[];
  evidence_gaps: EvidenceGap[];
  provider_letter_request_checklist: WorkflowTask[];
  appeal_strategy: string;
  draft_appeal_letter?: string | null;
  attachment_index: AttachmentIndexItem[];
  submission_plan: SubmissionPlan;
  follow_up_plan: FollowUpItem[];
  workflow_phase_checklist: WorkflowPhaseChecklistItem[];
  quality_checks: QualityCheck[];
  phi_scan: PhiScanSummary;
  retrieval_citations: RetrievedSourceSnippet[];
  human_review_required: boolean;
  warnings: string[];
  model_metadata: Record<string, unknown>;
  analyzed_at: string;
}

export interface DenialWorkflowExportRequest {
  workflow: DenialWorkflowAnalysisResponse;
  export_format: ExportFormat;
  filename_prefix?: string;
}

export interface DenialWorkflowExportResponse {
  filename: string;
  content_type: string;
  encoding: 'utf-8' | 'base64';
  content: string;
  generated_at: string;
}

export interface DenialWorkflowSourceRegistryItem {
  source_id: string;
  title: string;
  source_type: string;
  citation: string;
  payer_type?: string | null;
  phi_status: string;
  license_status: string;
}

export interface DenialWorkflowSourceRegistryResponse {
  sources: DenialWorkflowSourceRegistryItem[];
}

export interface DenialWorkflowStudentModelStatus {
  provider: string;
  base_url: string;
  model: string;
  fallback_model: string;
  adapter_path: string;
  adapter_path_exists: boolean;
  schema_contract_name: string;
  acceptance_report_path: string;
  readiness_report_path: string;
  accepted_for_denial_workflow: boolean;
  acceptance_release_ready?: boolean | null;
  readiness_distillation_ready?: boolean | null;
  readiness_release_ready?: boolean | null;
  benchmark_score_ratio?: number | null;
  warning_count?: number | null;
  blocked_count?: number | null;
  runtime_checked: boolean;
  runtime_available: boolean;
  runtime_status: string;
  runtime_error?: string | null;
  use_by_default: boolean;
  effective_use_by_default: boolean;
  default_cutover_ready: boolean;
  default_cutover_approved: boolean;
  default_approval_reference_configured: boolean;
  runtime_supervised: boolean;
  rollback_to_nvidia_enabled: boolean;
  default_cutover_blockers: string[];
  runtime_required_for_default: boolean;
  max_tokens: number;
  enable_thinking: boolean;
  server_command: string[];
  server_command_display: string;
  notes: string[];
}

export interface CorpusManifestIssue {
  document_id?: string | null;
  field: string;
  code: string;
  message: string;
}

export interface CorpusStatusResponse {
  manifest_path: string;
  manifest_exists: boolean;
  record_count: number;
  counts_by_deidentification_status: Record<string, number>;
  counts_by_document_role: Record<string, number>;
  counts_by_phi_status: Record<string, number>;
  training_eligible_count: number;
  blocked_count: number;
  missing_categories: string[];
  ready_for_training_export: boolean;
  issues: CorpusManifestIssue[];
}

export type CorpusDocumentRole =
  | 'denial_letter'
  | 'appeal_letter'
  | 'appeal_response'
  | 'policy'
  | 'rule_source'
  | 'template'
  | 'other';

export type CorpusIntakeState =
  | 'raw_quarantined'
  | 'machine_deidentified'
  | 'qa_failed'
  | 'human_review_required'
  | 'privacy_review_passed'
  | 'expert_determination_required'
  | 'training_eligible';

export type CorpusSplit = 'train' | 'valid' | 'test' | 'holdout' | 'none';
export type CorpusReviewMethod =
  | 'privacy_review'
  | 'expert_determination'
  | 'synthetic_fixture_review';
export type CorpusReviewDecision =
  | 'approve_for_training'
  | 'privacy_review_passed'
  | 'exclude';

export interface CorpusManifestRecord {
  source_id: string;
  document_id: string;
  pair_id?: string | null;
  source_type: string;
  document_role: CorpusDocumentRole;
  source_url_or_path: string;
  checksum: string;
  phi_status: PhiStatus;
  deidentification_status: CorpusIntakeState;
  license_status: string;
  review_status:
    | 'not_reviewed'
    | 'privacy_review_passed'
    | 'expert_determination_required'
    | 'training_approved'
    | 'excluded';
  residual_risk_score: number;
  training_eligible: boolean;
  split: CorpusSplit;
  micro_skill_ids: string[];
  payer_type?: string | null;
  denial_type?: string | null;
  appeal_route?: string | null;
  appeal_level?: string | null;
  outcome?: string | null;
  reviewer_id?: string | null;
  review_timestamp?: string | null;
  review_method?: string | null;
  training_decision_note?: string | null;
  review_findings: string[];
  reviewed_phi_finding_count: number;
  reviewed_contextual_risk_finding_count: number;
  privacy_review_completed: boolean;
  license_review_completed: boolean;
  residual_risk_review_completed: boolean;
  expert_determination_completed: boolean;
}

export interface CorpusReviewQueueItem {
  source_id: string;
  document_id: string;
  pair_id?: string | null;
  source_type: string;
  document_role: CorpusDocumentRole;
  phi_status: PhiStatus;
  deidentification_status: CorpusIntakeState;
  license_status: string;
  review_status: string;
  residual_risk_score: number;
  training_eligible: boolean;
  split: CorpusSplit;
  micro_skill_count: number;
  reviewer_present: boolean;
  review_timestamp_present: boolean;
  privacy_review_completed: boolean;
  license_review_completed: boolean;
  residual_risk_review_completed: boolean;
  expert_determination_completed: boolean;
  reviewed_phi_finding_count: number;
  reviewed_contextual_risk_finding_count: number;
  paired_denial_present: boolean;
  paired_appeal_present: boolean;
  ready_for_review_decision: boolean;
  ready_for_training_export: boolean;
  production_corpus_candidate: boolean;
  blockers: string[];
  next_action: string;
}

export interface CorpusReviewQueueResponse {
  manifest_path: string;
  manifest_exists: boolean;
  record_count: number;
  queue_item_count: number;
  needs_review_count: number;
  needs_expert_determination_count: number;
  missing_pair_count: number;
  training_eligible_count: number;
  production_candidate_count: number;
  values_redacted: boolean;
  items: CorpusReviewQueueItem[];
}

export interface CorpusDeidentifyRequest {
  document_text: string;
  source_id?: string;
  document_id?: string;
  document_role?: CorpusDocumentRole;
}

export interface CorpusReplacement {
  placeholder: string;
  finding_type: string;
  replacement_count: number;
}

export interface CorpusContextualRiskFinding {
  finding_type: string;
  line: number;
  column: number;
  severity: 'low' | 'medium' | 'high';
  category: 'contextual_reidentification_risk';
  surface?: string | null;
  review_action: string;
}

export interface CorpusDeidentifyResponse {
  source_id: string;
  document_id: string;
  deidentified_text: string;
  deidentification_status: CorpusIntakeState;
  phi_scan_before: PhiScanSummary;
  phi_scan_after: PhiScanSummary;
  replacements: CorpusReplacement[];
  residual_risk_score: number;
  contextual_risk_findings: CorpusContextualRiskFinding[];
  contextual_risk_finding_count: number;
  human_review_required: boolean;
  training_eligible: boolean;
  warnings: string[];
}

export interface CorpusDocumentSurfaceInspectRequest {
  source_id?: string;
  document_id?: string;
  document_role?: CorpusDocumentRole;
  source_filename?: string | null;
  source_mime_type?: string | null;
  visible_text?: string | null;
  hidden_text?: string | null;
  ocr_text?: string | null;
  scanned_page_texts?: string[];
  header_footer_text?: string | null;
  metadata?: Record<string, string>;
  barcode_qr_text?: string[];
  attachment_filenames?: string[];
}

export interface CorpusDocumentSurfaceScan {
  surface: string;
  item_count: number;
  text_length: number;
  phi_scan: PhiScanSummary;
  findings: PhiScanFinding[];
  contextual_risk_findings: CorpusContextualRiskFinding[];
  warnings: string[];
}

export interface CorpusDocumentSurfaceInspectResponse {
  source_id: string;
  document_id: string;
  document_role: CorpusDocumentRole;
  deidentification_status: CorpusIntakeState;
  residual_risk_score: number;
  human_review_required: boolean;
  training_eligible: boolean;
  values_redacted: boolean;
  surface_count: number;
  blocking_surface_count: number;
  contextual_risk_finding_count: number;
  contextual_risk_surface_count: number;
  surface_scans: CorpusDocumentSurfaceScan[];
  warnings: string[];
}

export interface CorpusReviewDecisionRequest {
  record: CorpusManifestRecord;
  reviewer_id: string;
  review_method: CorpusReviewMethod;
  decision: CorpusReviewDecision;
  phi_status?: PhiStatus | null;
  license_status: string;
  split: CorpusSplit;
  micro_skill_ids: string[];
  residual_risk_score: number;
  privacy_review_completed: boolean;
  license_review_completed: boolean;
  residual_risk_review_completed: boolean;
  expert_determination_completed: boolean;
  reviewed_phi_finding_count: number;
  reviewed_contextual_risk_finding_count: number;
  review_findings: string[];
  training_decision_note: string;
}

export interface CorpusReviewDecisionResponse {
  approved_for_training: boolean;
  record: CorpusManifestRecord;
  blockers: string[];
  warnings: string[];
  validation: CorpusStatusResponse;
}

export interface CorpusImportRequest {
  record: CorpusManifestRecord;
  document_text: string;
  chunk_size?: number;
  overlap?: number;
}

export interface CorpusImportResponse {
  imported: boolean;
  retrieval_source: RetrievalSourceResponse | null;
  validation: CorpusStatusResponse;
}

export interface RetrievalSourceCreateRequest {
  title: string;
  source_type: string;
  document_text: string;
  jurisdiction?: string | null;
  payer_type?: string | null;
  date?: string | null;
  source_url?: string | null;
  page_number?: string | null;
  section_label?: string | null;
  phi_status?: PhiStatus;
  license_status?: string;
  access_scope?: RetrievalSourceAccessScope;
  retention_until?: string | null;
  privacy_review_completed?: boolean;
  user_data_opt_in_for_model_improvement?: boolean;
  model_improvement_legal_approval_attested?: boolean;
  model_improvement_baa_attested?: boolean;
  model_improvement_consent_attested?: boolean;
  model_improvement_consent_notice_version?: string | null;
  chunk_size?: number;
  overlap?: number;
}

export interface RetrievalSourceResponse {
  id: number;
  source_id: string;
  title: string;
  source_type: string;
  jurisdiction?: string | null;
  payer_type?: string | null;
  date?: string | null;
  source_url?: string | null;
  phi_status: string;
  license_status: string;
  access_scope: RetrievalSourceAccessScope;
  retention_until?: string | null;
  deleted_at?: string | null;
  deleted_by_user_id?: number | null;
  deletion_reason?: string | null;
  chunk_count: number;
  embedding_model?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
}

export interface RetrievalSourceDeleteResponse {
  source_id: string;
  deleted: boolean;
  deleted_at: string;
  deleted_by_user_id?: number | null;
  deletion_reason: string;
}

export interface RetrievalSourceGovernanceSummary {
  active_count: number;
  deleted_count: number;
  expired_active_count: number;
  retained_without_expiration_count: number;
  counts_by_access_scope: Record<string, number>;
  counts_by_phi_status: Record<string, number>;
  counts_by_license_status: Record<string, number>;
}

export interface RetrievalVectorReadinessResponse {
  production_ready: boolean;
  embedding_backend: string;
  embedding_model: string;
  vector_backend: string;
  semantic_backend_configured: boolean;
  hash_fallback_in_use: boolean;
  active_source_count: number;
  chunk_count: number;
  stored_embedding_models: Record<string, number>;
  sources_requiring_reindex_count: number;
  blockers: string[];
  warnings: string[];
  notes: string[];
}

export interface RetrievalAuditEvent {
  id: number;
  action: string;
  user_id?: number | null;
  timestamp: string;
  details: Record<string, string | number | boolean | null>;
}

export interface RetrievalAuditDashboardResponse {
  event_count: number;
  source_id?: string | null;
  counts_by_action: Record<string, number>;
  events: RetrievalAuditEvent[];
}

export interface ModelImprovementComplianceStatus {
  enabled: boolean;
  legal_approval_confirmed: boolean;
  baa_confirmed: boolean;
  consent_notice_version?: string | null;
  approval_reference_configured: boolean;
  ready: boolean;
  blockers: string[];
}

export interface ClaimResponse {
  id: number;
  patient_id: number;
  provider_id: number;
  claim_data: Record<string, any>;
  diagnosis_codes?: string[];
  procedure_codes?: string[];
  submission_date: string;
  status: string;
  denial_prediction?: number;
  denial_confidence?: number;
  denial_reasons?: DenialReason[];
  recommendations?: Recommendation[];
  human_review_required: boolean;
  human_review_status: HumanReviewStatus;
  human_review_reasons: string[];
  human_review_threshold: number;
  human_review_next_action: string;
  document_filename?: string | null;
  document_governance?: ClaimDocumentGovernance | null;
  document_available: boolean;
  created_at: string;
  patient?: PatientResponse | null;
}

export interface ClaimDocumentGovernance {
  access_scope: string;
  retention_until?: string | null;
  deleted_at?: string | null;
  deleted_by_user_id?: number | null;
  deletion_reason?: string | null;
  created_by_user_id?: number | null;
  is_retired: boolean;
  is_retention_expired: boolean;
  can_view_document: boolean;
  can_retire_document: boolean;
}

export interface ClaimDocumentGovernanceSummary {
  active_count: number;
  deleted_count: number;
  expired_active_count: number;
  retained_without_expiration_count: number;
  counts_by_access_scope: Record<string, number>;
}

export interface ClaimDocumentAuditEvent {
  id: number;
  action: string;
  user_id?: number | null;
  claim_id?: number | null;
  timestamp: string;
  details: Record<string, any>;
}

export interface ClaimDocumentAuditDashboardResponse {
  event_count: number;
  claim_id?: number | null;
  counts_by_action: Record<string, number>;
  events: ClaimDocumentAuditEvent[];
}

export interface ClaimDocumentDeleteResponse {
  claim_id: number;
  deleted: boolean;
  deleted_at: string;
  deleted_by_user_id?: number | null;
  deletion_reason: string;
}

export interface DocumentAnalysisRequest {
  document_text: string;
  document_type?: string;
}

export interface DocumentAnalysisResponse {
  claim_id?: number;
  document_type: string;
  payer_name: string | null;
  denial_reason: string | null;
  denial_code: string | null;
  claim_amount: number | null;
  service_date: string | null;
  patient_name: string | null;
  policy_number: string | null;
  extracted_codes: string[];
  analysis: string;
  recommendations: Recommendation[];
  appeal_strategy: string | null;
  ocr_engine?: string | null;
  ocr_model?: string | null;
  ocr_pages?: number | null;
  ocr_duration_ms?: number | null;
  ocr_warnings?: string[] | null;
  document_surface_inspection?: CorpusDocumentSurfaceInspectResponse | null;
  analyzed_at?: string;
  denial_workflow?: DenialWorkflowAnalysisResponse | null;
}

export interface BatchDocumentAnalysisDocument {
  document_text: string;
}

export interface BatchDocumentAnalysisRequest {
  documents: BatchDocumentAnalysisDocument[];
  document_type?: string;
}

export interface BatchDocumentAnalysisResponse {
  total: number;
  successful: number;
  failed: number;
  results: DocumentAnalysisResponse[];
}

export interface ClaimDocument {
  claim_id: number;
  filename: string | null;
  document_text: string;
  governance: ClaimDocumentGovernance;
}

export interface AppealGenerateRequest {
  claim_id: number;
  appeal_reason: string;
  additional_context?: string;
}

export interface AppealGenerateResponse {
  claim_id: number;
  appeal_letter: string;
  supporting_evidence: string[];
  generated_at: string;
}

export const claimsApi = {
  predict: (data: ClaimData) => api.post<ClaimPredictionResponse>('/claims/predict', data),
  submit: (data: ClaimData) => api.post<ClaimSubmitResponse>('/claims/submit', data),
  getClaim: (id: number) => api.get(`/claims/${id}`),
  listClaims: (skip = 0, limit = 50) => api.get<ClaimResponse[]>(`/claims/?skip=${skip}&limit=${limit}`),
  documentGovernanceSummary: () =>
    api.get<ClaimDocumentGovernanceSummary>('/claims/documents/governance-summary'),
  documentAuditDashboard: (claimId?: number, limit = 100) =>
    api.get<ClaimDocumentAuditDashboardResponse>('/claims/documents/audit', {
      params: { claim_id: claimId, limit },
    }),
  analyzeDocument: (data: DocumentAnalysisRequest) => api.post<DocumentAnalysisResponse>('/claims/analyze-document', data),
  analyzeDocumentsBatch: (data: BatchDocumentAnalysisRequest) =>
    api.post<BatchDocumentAnalysisResponse>('/claims/analyze-documents-batch', data),
  uploadDocument: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<DocumentAnalysisResponse>('/claims/upload-document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getClaimDocument: (id: number) => api.get<ClaimDocument>(`/claims/${id}/document`),
  retireClaimDocument: (id: number, deletionReason = 'retention_or_privacy_review') =>
    api.post<ClaimDocumentDeleteResponse>(`/claims/${id}/document/delete`, {
      deletion_reason: deletionReason,
    }),
};

export const analyticsApi = {
  getDenialTrends: (days = 30) => api.get(`/analytics/denial-trends?days=${days}`),
  getSummary: () => api.get('/analytics/summary'),
};

export const appealsApi = {
  generate: (claimId: number, appealReason: string, additionalContext?: string) =>
    api.post<AppealGenerateResponse>('/appeals/generate', {
      claim_id: claimId,
      appeal_reason: appealReason,
      additional_context: additionalContext,
    } satisfies AppealGenerateRequest),
};

export const denialWorkflowApi = {
  analyze: (data: DenialWorkflowAnalysisRequest) => api.post<DenialWorkflowAnalysisResponse>('/denial-workflow/analyze', data),
  exportPacket: (data: DenialWorkflowExportRequest) =>
    api.post<DenialWorkflowExportResponse>('/denial-workflow/export', data),
  sourceRegistry: () => api.get<DenialWorkflowSourceRegistryResponse>('/denial-workflow/source-registry'),
  studentModelStatus: () => api.get<DenialWorkflowStudentModelStatus>('/denial-workflow/student-model/status'),
  modelImprovementComplianceStatus: () =>
    api.get<ModelImprovementComplianceStatus>('/denial-workflow/model-improvement/compliance-status'),
  corpusStatus: () => api.get<CorpusStatusResponse>('/denial-workflow/corpus/status'),
  corpusReviewQueue: () => api.get<CorpusReviewQueueResponse>('/denial-workflow/corpus/review-queue'),
  createSource: (data: RetrievalSourceCreateRequest) =>
    api.post<RetrievalSourceResponse>('/denial-workflow/sources', data),
  listSources: () => api.get<RetrievalSourceResponse[]>('/denial-workflow/sources'),
  sourceGovernanceSummary: () =>
    api.get<RetrievalSourceGovernanceSummary>('/denial-workflow/sources/governance-summary'),
  retrievalVectorReadiness: () =>
    api.get<RetrievalVectorReadinessResponse>('/denial-workflow/sources/vector-readiness'),
  deleteSource: (sourceId: string, deletionReason = 'ui_retention_or_privacy_review') =>
    api.post<RetrievalSourceDeleteResponse>(
      `/denial-workflow/sources/${encodeURIComponent(sourceId)}/delete`,
      { deletion_reason: deletionReason },
    ),
  retrievalAuditDashboard: (sourceId?: string, limit = 25) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (sourceId) query.set('source_id', sourceId);
    return api.get<RetrievalAuditDashboardResponse>(`/denial-workflow/audit/retrieval-documents?${query.toString()}`);
  },
  inspectCorpusDocument: (data: CorpusDocumentSurfaceInspectRequest) =>
    api.post<CorpusDocumentSurfaceInspectResponse>('/denial-workflow/corpus/inspect-document', data),
  deidentifyCorpusDocument: (data: CorpusDeidentifyRequest) =>
    api.post<CorpusDeidentifyResponse>('/denial-workflow/corpus/deidentify', data),
  reviewCorpusDecision: (data: CorpusReviewDecisionRequest) =>
    api.post<CorpusReviewDecisionResponse>('/denial-workflow/corpus/review-decision', data),
  importApprovedCorpusDocument: (data: CorpusImportRequest) =>
    api.post<CorpusImportResponse>('/denial-workflow/corpus/import-approved', data),
};

export default api;
