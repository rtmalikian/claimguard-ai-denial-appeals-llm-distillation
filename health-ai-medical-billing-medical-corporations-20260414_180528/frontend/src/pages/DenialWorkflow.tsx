import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { denialWorkflowApi } from '../api/client';
import SafeHtml from '../components/common/SafeHtml';
import type {
  AuthUser,
  CorpusDeidentifyResponse,
  CorpusDocumentRole,
  CorpusDocumentSurfaceInspectResponse,
  CorpusImportResponse,
  CorpusManifestRecord,
  CorpusReviewDecisionResponse,
  CorpusReviewQueueResponse,
  CorpusSplit,
  CorpusStatusResponse,
  DenialWorkflowAnalysisResponse,
  DenialWorkflowSourceRegistryItem,
  DenialWorkflowStudentModelStatus,
  EvidenceGap,
  ExportFormat,
  FactItem,
  ModelImprovementComplianceStatus,
  PhiStatus,
  QualityCheck,
  RetrievalAuditDashboardResponse,
  RetrievalSourceAccessScope,
  RetrievalSourceGovernanceSummary,
  RetrievalSourceResponse,
  RetrievalVectorReadinessResponse,
  WorkflowPhaseChecklistItem,
  WorkflowTask,
} from '../api/client';

interface DenialWorkflowProps {
  currentUser: AuthUser | null;
}

interface BadgeProps {
  label: string;
  className: string;
}

const DOCUMENT_TYPES = [
  { value: 'denial_letter', label: 'Denial letter' },
  { value: 'eob', label: 'EOB' },
  { value: 'era', label: 'ERA' },
  { value: 'payer_portal_notice', label: 'Payer portal notice' },
  { value: 'provider_note', label: 'Provider note' },
];

const PHI_STATUSES: { value: PhiStatus; label: string }[] = [
  { value: 'contains_phi', label: 'Contains PHI' },
  { value: 'deidentified', label: 'De-identified' },
  { value: 'no_phi', label: 'No PHI' },
  { value: 'unknown', label: 'Unknown' },
];

const ACCESS_SCOPE_OPTIONS: { value: RetrievalSourceAccessScope; label: string }[] = [
  { value: 'owner', label: 'Owner' },
  { value: 'billing_team', label: 'Billing team' },
  { value: 'admin_only', label: 'Admin only' },
];

const CORPUS_DOCUMENT_ROLES: { value: CorpusDocumentRole; label: string }[] = [
  { value: 'denial_letter', label: 'Denial letter' },
  { value: 'appeal_letter', label: 'Appeal letter' },
  { value: 'appeal_response', label: 'Appeal response' },
  { value: 'policy', label: 'Policy' },
  { value: 'rule_source', label: 'Rule source' },
  { value: 'template', label: 'Template' },
  { value: 'other', label: 'Other' },
];

const CORPUS_TRAINING_SPLITS: { value: Extract<CorpusSplit, 'train' | 'valid' | 'test'>; label: string }[] = [
  { value: 'train', label: 'Train' },
  { value: 'valid', label: 'Validation' },
  { value: 'test', label: 'Test' },
];

const EXPORT_FORMATS: ExportFormat[] = ['markdown', 'docx', 'pdf'];
const DEFAULT_MICRO_SKILLS = 'MS01, MS02, MS03, MS04, MS05, MS06, MS07, MS08, MS09, MS10, MS11, MS12';

const defaultSourceForm = {
  title: 'Reviewed de-identified denial source',
  sourceType: 'corpus_denial_letter',
  documentText: '',
  jurisdiction: '',
  payerType: '',
  sourceUrl: '',
  sectionLabel: '',
  phiStatus: 'deidentified' as PhiStatus,
  licenseStatus: 'reviewed_allowed',
  accessScope: 'owner' as RetrievalSourceAccessScope,
  retentionUntil: '',
  privacyReviewCompleted: false,
  modelImprovementOptIn: false,
  modelImprovementLegalAttestation: false,
  modelImprovementBaaAttestation: false,
  modelImprovementConsentAttestation: false,
  modelImprovementConsentNoticeVersion: '',
};

const defaultCorpusForm = {
  sourceId: 'SRC-UI-CANDIDATE',
  documentId: 'DOC-UI-CANDIDATE',
  pairId: '',
  documentRole: 'denial_letter' as CorpusDocumentRole,
  sourceFilename: 'deidentified-denial-example.txt',
  sourceMimeType: 'text/plain',
  visibleText: '',
  hiddenText: '',
  ocrText: '',
  headerFooterText: '',
  metadataText: '',
  barcodeText: '',
  attachmentFilenames: '',
  payerType: 'commercial',
  denialType: 'missing_documentation',
  appealRoute: 'internal_appeal',
  appealLevel: 'first_level',
  outcome: 'reviewed_import',
  licenseStatus: 'reviewed_allowed',
  phiStatus: 'deidentified' as PhiStatus,
  microSkillIds: DEFAULT_MICRO_SKILLS,
  trainingSplit: 'train' as Extract<CorpusSplit, 'train' | 'valid' | 'test'>,
  privacyReviewCompleted: false,
  licenseReviewCompleted: false,
  residualRiskReviewCompleted: false,
  expertDeterminationCompleted: false,
  trainingApproved: false,
};

const CORPUS_SCAN_INPUT_FIELDS = new Set<keyof typeof defaultCorpusForm>([
  'sourceId',
  'documentId',
  'documentRole',
  'sourceFilename',
  'sourceMimeType',
  'visibleText',
  'hiddenText',
  'ocrText',
  'headerFooterText',
  'metadataText',
  'barcodeText',
  'attachmentFilenames',
]);

const getErrorMessage = (err: unknown) => {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item) => String(item)).join(', ');
  }
  return 'Request failed';
};

const readableLabel = (value: string) => value.replace(/_/g, ' ');

const valueToText = (value: unknown) => {
  if (value === null || value === undefined || value === '') return 'N/A';
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'N/A';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const splitLines = (value: string) => value
  .split('\n')
  .map((item) => item.trim())
  .filter(Boolean);

const parseCommaList = (value: string) => value
  .split(',')
  .map((item) => item.trim().toUpperCase())
  .filter(Boolean);

const parseMetadata = (value: string) => {
  const metadata: Record<string, string> = {};
  for (const line of splitLines(value)) {
    const separatorIndex = line.indexOf(':');
    if (separatorIndex <= 0) continue;
    const key = line.slice(0, separatorIndex).trim();
    const itemValue = line.slice(separatorIndex + 1).trim();
    if (key && itemValue) metadata[key] = itemValue;
  }
  return metadata;
};

const sha256Text = async (value: string) => {
  if (!window.crypto?.subtle) {
    throw new Error('Browser SHA-256 support is required for approved corpus import.');
  }
  const digest = await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return `sha256:${Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')}`;
};

const formatDate = (value?: string | null) => {
  if (!value) return 'Needs verification';
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
};

const formatDateTime = (value?: string | null) => {
  if (!value) return 'No expiration';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const sourceLabel = (source: FactItem['source']) => {
  const pieces = [
    readableLabel(source.source_status),
    source.source_title,
    source.source_document_id,
  ].filter(Boolean);
  return pieces.join(' | ');
};

const sourceStatusClass = (status: FactItem['source']['source_status']) => {
  if (status === 'known_from_documents') return 'bg-green-50 text-green-700 ring-green-200';
  if (status === 'cited_rule') return 'bg-blue-50 text-blue-700 ring-blue-200';
  if (status === 'inferred') return 'bg-yellow-50 text-yellow-800 ring-yellow-200';
  return 'bg-red-50 text-red-700 ring-red-200';
};

const qualityClass = (status: QualityCheck['status']) => {
  if (status === 'pass') return 'bg-green-50 text-green-700';
  if (status === 'warning') return 'bg-yellow-50 text-yellow-800';
  return 'bg-red-50 text-red-700';
};

const priorityClass = (priority: EvidenceGap['priority']) => {
  if (priority === 'high') return 'bg-red-50 text-red-700 ring-red-200';
  if (priority === 'medium') return 'bg-yellow-50 text-yellow-800 ring-yellow-200';
  return 'bg-green-50 text-green-700 ring-green-200';
};

const phaseStatusClass = (status: WorkflowPhaseChecklistItem['status']) => {
  if (status === 'ready_for_human_review') return 'bg-green-50 text-green-700 ring-green-200';
  if (status === 'in_progress') return 'bg-blue-50 text-blue-700 ring-blue-200';
  if (status === 'blocked') return 'bg-red-50 text-red-700 ring-red-200';
  return 'bg-gray-50 text-gray-700 ring-gray-200';
};

const phiStatusClass = (reviewRequired: boolean) => (
  reviewRequired ? 'bg-red-50 text-red-700 ring-red-200' : 'bg-green-50 text-green-700 ring-green-200'
);

const downloadExport = (filename: string, contentType: string, encoding: 'utf-8' | 'base64', content: string) => {
  let blob: Blob;
  if (encoding === 'base64') {
    const binary = window.atob(content);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    blob = new Blob([bytes], { type: contentType });
  } else {
    blob = new Blob([content], { type: contentType });
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

function Badge({ label, className }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${className}`}>
      {label}
    </span>
  );
}

function FactRows({ title, facts }: { title: string; facts: FactItem[] }) {
  return (
    <section className="bg-white p-6 shadow">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">{title}</h2>
      {facts.length === 0 ? (
        <p className="text-sm text-gray-500">No facts returned.</p>
      ) : (
        <div className="space-y-3">
          {facts.map((fact, index) => (
            <div key={`${fact.field}-${index}`} className="border-b border-gray-100 pb-3 last:border-b-0 last:pb-0">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <SafeHtml value={readableLabel(fact.field)} className="text-sm font-medium text-gray-900" />
                  <SafeHtml value={valueToText(fact.value)} className="mt-1 text-sm text-gray-700" />
                </div>
                <Badge label={readableLabel(fact.source.source_status)} className={sourceStatusClass(fact.source.source_status)} />
              </div>
              <SafeHtml value={sourceLabel(fact.source)} className="mt-2 text-xs text-gray-500" />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function TaskList({ title, tasks }: { title: string; tasks: WorkflowTask[] }) {
  return (
    <section className="bg-white p-6 shadow">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">{title}</h2>
      {tasks.length === 0 ? (
        <p className="text-sm text-gray-500">No open tasks returned.</p>
      ) : (
        <div className="space-y-3">
          {tasks.map((task, index) => (
            <div key={`${task.task}-${index}`} className="rounded-md border border-gray-200 p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <SafeHtml value={task.task} className="text-sm font-medium text-gray-900" />
                  {task.reason && <SafeHtml value={task.reason} className="mt-1 text-sm text-gray-600" />}
                </div>
                <Badge label={readableLabel(task.verification_status)} className="bg-gray-50 text-gray-700 ring-gray-200" />
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-3">
                <div>Owner: <SafeHtml value={task.owner} inline /></div>
                <div>Due: {formatDate(task.due_date)}</div>
                <SafeHtml value={sourceLabel(task.source)} />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EvidenceGapList({ gaps }: { gaps: EvidenceGap[] }) {
  return (
    <section className="bg-white p-6 shadow">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">Evidence Gaps</h2>
      {gaps.length === 0 ? (
        <p className="text-sm text-gray-500">No evidence gaps returned.</p>
      ) : (
        <div className="space-y-3">
          {gaps.map((gap, index) => (
            <div key={`${gap.evidence_type}-${index}`} className="rounded-md border border-gray-200 p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <SafeHtml value={readableLabel(gap.evidence_type)} className="text-sm font-medium text-gray-900" />
                  <SafeHtml value={gap.description} className="mt-1 text-sm text-gray-700" />
                </div>
                <Badge label={gap.priority} className={priorityClass(gap.priority)} />
              </div>
              <div className="mt-3 text-xs text-gray-500">
                Owner: <SafeHtml value={gap.owner} inline /> | Human verification: {gap.human_verification_required ? 'yes' : 'no'}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SourceRegistry({ sources, error }: { sources: DenialWorkflowSourceRegistryItem[]; error: string | null }) {
  return (
    <section className="bg-white p-6 shadow">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">Built-In Sources</h2>
      {error && <SafeHtml value={error} className="mb-3 rounded-md bg-yellow-50 p-3 text-sm text-yellow-800" />}
      {sources.length === 0 ? (
        <p className="text-sm text-gray-500">No source metadata loaded.</p>
      ) : (
        <div className="space-y-3">
          {sources.slice(0, 5).map((source) => (
            <div key={source.source_id} className="border-b border-gray-100 pb-3 last:border-b-0 last:pb-0">
              <SafeHtml value={source.title} className="text-sm font-medium text-gray-900" />
              <SafeHtml value={source.citation} className="mt-1 text-xs text-gray-500" />
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge label={source.source_type} className="bg-gray-50 text-gray-700 ring-gray-200" />
                <Badge label={source.phi_status} className="bg-green-50 text-green-700 ring-green-200" />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function StudentModelStatus({
  status,
  error,
}: {
  status: DenialWorkflowStudentModelStatus | null;
  error: string | null;
}) {
  return (
    <section className="bg-white p-6 shadow">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">Distilled Student</h2>
      {error && <SafeHtml value={error} className="mb-3 rounded-md bg-yellow-50 p-3 text-sm text-yellow-800" />}
      {!status ? (
        <p className="text-sm text-gray-500">Student model status is unavailable.</p>
      ) : (
        <div className="space-y-3 text-sm text-gray-700">
          <div className="flex flex-wrap gap-2">
            <Badge
              label={status.accepted_for_denial_workflow ? 'accepted' : 'not accepted'}
              className={status.accepted_for_denial_workflow ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-red-50 text-red-700 ring-red-200'}
            />
            <Badge
              label={status.runtime_available ? 'runtime online' : `runtime ${status.runtime_checked ? 'offline' : 'not checked'}`}
              className={status.runtime_available ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-yellow-50 text-yellow-800 ring-yellow-200'}
            />
            <Badge label={status.schema_contract_name} className="bg-blue-50 text-blue-700 ring-blue-200" />
          </div>
          <div>
            <div className="text-gray-500">Model</div>
            <SafeHtml value={status.model} className="font-medium text-gray-900" />
          </div>
          <div>
            <div className="text-gray-500">Adapter</div>
            <div className="font-medium text-gray-900">{status.adapter_path_exists ? 'present' : 'missing'}</div>
          </div>
          <div>
            <div className="text-gray-500">Benchmark</div>
            <div className="font-medium text-gray-900">
              {status.benchmark_score_ratio === null || status.benchmark_score_ratio === undefined
                ? 'N/A'
                : status.benchmark_score_ratio.toFixed(4)}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <div className="text-gray-500">Use by default</div>
              <div className="font-medium text-gray-900">
                {status.effective_use_by_default ? 'active' : status.use_by_default ? 'requested, blocked' : 'disabled'}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Runtime status</div>
              <div className="font-medium text-gray-900">
                <SafeHtml
                  value={`${readableLabel(status.runtime_status)}${status.runtime_error ? ` (${status.runtime_error})` : ''}`}
                  inline
                />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <div className="text-gray-500">Cutover approval</div>
              <div className="font-medium text-gray-900">
                {status.default_cutover_approved && status.default_approval_reference_configured ? 'configured' : 'not configured'}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Runtime supervision</div>
              <div className="font-medium text-gray-900">{status.runtime_supervised ? 'configured' : 'not configured'}</div>
            </div>
          </div>
          {status.rollback_to_nvidia_enabled && (
            <div className="rounded-md bg-blue-50 p-3 text-xs text-blue-800">
              Rollback to NVIDIA/deterministic fallback is enabled.
            </div>
          )}
          {status.default_cutover_blockers.length > 0 && (
            <div className="rounded-md bg-yellow-50 p-3 text-xs text-yellow-800">
              <div className="font-medium">Default cutover blockers</div>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {status.default_cutover_blockers.map((blocker) => (
                  <li key={blocker}><SafeHtml value={blocker} /></li>
                ))}
              </ul>
            </div>
          )}
          {status.server_command_display && (
            <div>
              <div className="mb-1 text-gray-500">Launch command</div>
              <pre className="max-h-40 overflow-auto rounded-md bg-gray-950 p-3 text-xs text-gray-100">
                <code><SafeHtml value={status.server_command_display} inline /></code>
              </pre>
            </div>
          )}
          {status.notes.slice(0, 4).map((note, index) => (
            <div key={`${note}-${index}`} className="rounded-md bg-gray-50 p-3 text-xs text-gray-600">
              <SafeHtml value={note} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function CorpusReadinessPanel({ status, error }: { status: CorpusStatusResponse | null; error: string | null }) {
  return (
    <section className="bg-white p-6 shadow">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Corpus Readiness</h2>
        {status && (
          <Badge
            label={status.ready_for_training_export ? 'training ready' : 'blocked'}
            className={status.ready_for_training_export ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-red-50 text-red-700 ring-red-200'}
          />
        )}
      </div>
      {error ? (
        <SafeHtml value={error} className="text-sm text-red-700" />
      ) : !status ? (
        <p className="text-sm text-gray-500">Corpus readiness unavailable.</p>
      ) : (
        <div className="space-y-3 text-sm text-gray-700">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md bg-gray-50 p-3">
              <div className="text-gray-500">Records</div>
              <div className="mt-1 font-medium text-gray-900">{status.record_count}</div>
            </div>
            <div className="rounded-md bg-gray-50 p-3">
              <div className="text-gray-500">Training Eligible</div>
              <div className="mt-1 font-medium text-gray-900">{status.training_eligible_count}</div>
            </div>
            <div className="rounded-md bg-gray-50 p-3">
              <div className="text-gray-500">Blocked</div>
              <div className="mt-1 font-medium text-gray-900">{status.blocked_count}</div>
            </div>
            <div className="rounded-md bg-gray-50 p-3">
              <div className="text-gray-500">Missing</div>
              <div className="mt-1 font-medium text-gray-900">{status.missing_categories.length}</div>
            </div>
          </div>
          {status.missing_categories.length > 0 && (
            <div className="rounded-md bg-yellow-50 p-3 text-yellow-800">
              {status.missing_categories.slice(0, 6).join(', ')}
              {status.missing_categories.length > 6 ? ' ...' : ''}
            </div>
          )}
          <div className="text-xs text-gray-500">
            Manifest: {status.manifest_exists ? status.manifest_path : 'not found'}
          </div>
        </div>
      )}
    </section>
  );
}

function CorpusAdminPanel({
  currentUser,
  onCorpusStatusRefresh,
}: {
  currentUser: AuthUser;
  onCorpusStatusRefresh: () => Promise<void>;
}) {
  const [sourceForm, setSourceForm] = useState(defaultSourceForm);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceNotice, setSourceNotice] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [storedSources, setStoredSources] = useState<RetrievalSourceResponse[]>([]);
  const [storedSourcesError, setStoredSourcesError] = useState<string | null>(null);
  const [governanceSummary, setGovernanceSummary] = useState<RetrievalSourceGovernanceSummary | null>(null);
  const [auditDashboard, setAuditDashboard] = useState<RetrievalAuditDashboardResponse | null>(null);
  const [modelImprovementStatus, setModelImprovementStatus] = useState<ModelImprovementComplianceStatus | null>(null);
  const [vectorReadiness, setVectorReadiness] = useState<RetrievalVectorReadinessResponse | null>(null);
  const [corpusReviewQueue, setCorpusReviewQueue] = useState<CorpusReviewQueueResponse | null>(null);
  const [governanceLoading, setGovernanceLoading] = useState(false);
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);

  const [corpusForm, setCorpusForm] = useState(defaultCorpusForm);
  const [surfaceInspection, setSurfaceInspection] = useState<CorpusDocumentSurfaceInspectResponse | null>(null);
  const [deidentifyResult, setDeidentifyResult] = useState<CorpusDeidentifyResponse | null>(null);
  const [corpusReviewDecision, setCorpusReviewDecision] = useState<CorpusReviewDecisionResponse | null>(null);
  const [corpusImportResult, setCorpusImportResult] = useState<CorpusImportResponse | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);
  const [deidentifyLoading, setDeidentifyLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [corpusNotice, setCorpusNotice] = useState<string | null>(null);
  const [corpusError, setCorpusError] = useState<string | null>(null);

  const refreshStoredSourceGovernance = useCallback(async () => {
    setGovernanceLoading(true);
    try {
      const auditRequest = currentUser.role === 'admin'
        ? denialWorkflowApi.retrievalAuditDashboard(undefined, 25)
        : Promise.resolve(null);
      const vectorReadinessRequest = currentUser.role === 'admin'
        ? denialWorkflowApi.retrievalVectorReadiness()
        : Promise.resolve(null);
      const [sourcesResult, summaryResult, auditResult, vectorResult, modelImprovementResult, reviewQueueResult] = await Promise.allSettled([
        denialWorkflowApi.listSources(),
        denialWorkflowApi.sourceGovernanceSummary(),
        auditRequest,
        vectorReadinessRequest,
        denialWorkflowApi.modelImprovementComplianceStatus(),
        denialWorkflowApi.corpusReviewQueue(),
      ]);

      if (sourcesResult.status === 'fulfilled') {
        setStoredSources(sourcesResult.value.data);
        setStoredSourcesError(null);
      } else {
        setStoredSourcesError('Stored retrieval sources are unavailable.');
      }

      if (summaryResult.status === 'fulfilled') {
        setGovernanceSummary(summaryResult.value.data);
      }

      if (auditResult.status === 'fulfilled' && auditResult.value) {
        setAuditDashboard(auditResult.value.data);
      } else if (currentUser.role !== 'admin') {
        setAuditDashboard(null);
      }

      if (modelImprovementResult.status === 'fulfilled') {
        setModelImprovementStatus(modelImprovementResult.value.data);
      } else {
        setModelImprovementStatus(null);
      }

      if (vectorResult.status === 'fulfilled' && vectorResult.value) {
        setVectorReadiness(vectorResult.value.data);
      } else if (currentUser.role !== 'admin') {
        setVectorReadiness(null);
      }

      if (reviewQueueResult.status === 'fulfilled') {
        setCorpusReviewQueue(reviewQueueResult.value.data);
      } else {
        setCorpusReviewQueue(null);
      }
    } finally {
      setGovernanceLoading(false);
    }
  }, [currentUser.role]);

  useEffect(() => {
    void refreshStoredSourceGovernance();
  }, [refreshStoredSourceGovernance]);

  const updateCorpusField = <K extends keyof typeof defaultCorpusForm>(
    field: K,
    value: (typeof defaultCorpusForm)[K],
  ) => {
    setCorpusForm((current) => ({ ...current, [field]: value }));
    if (CORPUS_SCAN_INPUT_FIELDS.has(field)) {
      setSurfaceInspection(null);
      setDeidentifyResult(null);
    }
    setCorpusReviewDecision(null);
    setCorpusImportResult(null);
    setCorpusNotice(null);
    setCorpusError(null);
  };

  const importReadiness = useMemo(() => {
    const microSkillIds = parseCommaList(corpusForm.microSkillIds);
    const contextualRiskFindingCount = (
      (surfaceInspection?.contextual_risk_finding_count ?? 0)
      + (deidentifyResult?.contextual_risk_finding_count ?? 0)
    );
    const requiresExpertDetermination = Boolean(
      contextualRiskFindingCount > 0
      || surfaceInspection?.deidentification_status === 'expert_determination_required'
      || deidentifyResult?.deidentification_status === 'expert_determination_required',
    );
    const surfacesClean = Boolean(
      surfaceInspection
      && surfaceInspection.blocking_surface_count === 0
      && surfaceInspection.residual_risk_score <= 0.2,
    );
    const deidentifiedClean = Boolean(
      deidentifyResult
      && deidentifyResult.phi_scan_after.finding_count === 0
      && deidentifyResult.residual_risk_score <= 0.2
      && deidentifyResult.deidentified_text.trim().length >= 20,
    );
    const reviewAttestationsPresent = Boolean(
      corpusForm.privacyReviewCompleted
      && corpusForm.licenseReviewCompleted
      && corpusForm.residualRiskReviewCompleted
      && corpusForm.trainingApproved
      && (!requiresExpertDetermination || corpusForm.expertDeterminationCompleted),
    );
    return {
      ready: surfacesClean && deidentifiedClean && reviewAttestationsPresent && microSkillIds.length > 0,
      surfacesClean,
      deidentifiedClean,
      reviewAttestationsPresent,
      requiresExpertDetermination,
      contextualRiskFindingCount,
      microSkillIds,
    };
  }, [corpusForm, deidentifyResult, surfaceInspection]);

  const handleCreateSource = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSourceLoading(true);
    setSourceNotice(null);
    setSourceError(null);

    try {
      const response = await denialWorkflowApi.createSource({
        title: sourceForm.title.trim(),
        source_type: sourceForm.sourceType.trim(),
        document_text: sourceForm.documentText.trim(),
        jurisdiction: sourceForm.jurisdiction.trim() || null,
        payer_type: sourceForm.payerType.trim() || null,
        source_url: sourceForm.sourceUrl.trim() || null,
        section_label: sourceForm.sectionLabel.trim() || null,
        phi_status: sourceForm.phiStatus,
        license_status: sourceForm.licenseStatus.trim() || 'review_required',
        access_scope: sourceForm.accessScope,
        retention_until: sourceForm.retentionUntil
          ? new Date(sourceForm.retentionUntil).toISOString()
          : null,
        privacy_review_completed: sourceForm.privacyReviewCompleted,
        user_data_opt_in_for_model_improvement: sourceForm.modelImprovementOptIn,
        model_improvement_legal_approval_attested: sourceForm.modelImprovementLegalAttestation,
        model_improvement_baa_attested: sourceForm.modelImprovementBaaAttestation,
        model_improvement_consent_attested: sourceForm.modelImprovementConsentAttestation,
        model_improvement_consent_notice_version: sourceForm.modelImprovementConsentNoticeVersion.trim() || null,
      });
      setStoredSources((current) => [response.data, ...current].slice(0, 10));
      setSourceNotice(`Stored source ${response.data.source_id} with ${response.data.chunk_count} chunk(s).`);
      await refreshStoredSourceGovernance();
    } catch (err) {
      setSourceError(getErrorMessage(err));
    } finally {
      setSourceLoading(false);
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    setDeleteSourceId(sourceId);
    setSourceNotice(null);
    setSourceError(null);
    try {
      await denialWorkflowApi.deleteSource(sourceId);
      setStoredSources((current) => current.filter((source) => source.source_id !== sourceId));
      setSourceNotice(`Retired source ${sourceId}.`);
      await refreshStoredSourceGovernance();
    } catch (err) {
      setSourceError(getErrorMessage(err));
    } finally {
      setDeleteSourceId(null);
    }
  };

  const handleInspectSurfaces = async () => {
    setInspectLoading(true);
    setCorpusNotice(null);
    setCorpusError(null);
    setSurfaceInspection(null);
    setCorpusReviewDecision(null);
    setCorpusImportResult(null);

    try {
      const response = await denialWorkflowApi.inspectCorpusDocument({
        source_id: corpusForm.sourceId.trim() || 'SRC-UI-CANDIDATE',
        document_id: corpusForm.documentId.trim() || 'DOC-UI-CANDIDATE',
        document_role: corpusForm.documentRole,
        source_filename: corpusForm.sourceFilename.trim() || null,
        source_mime_type: corpusForm.sourceMimeType.trim() || null,
        visible_text: corpusForm.visibleText.trim() || null,
        hidden_text: corpusForm.hiddenText.trim() || null,
        ocr_text: corpusForm.ocrText.trim() || null,
        header_footer_text: corpusForm.headerFooterText.trim() || null,
        metadata: parseMetadata(corpusForm.metadataText),
        barcode_qr_text: splitLines(corpusForm.barcodeText),
        attachment_filenames: splitLines(corpusForm.attachmentFilenames),
      });
      setSurfaceInspection(response.data);
      setCorpusNotice(
        response.data.blocking_surface_count
          ? 'Surface inspection requires review before import.'
          : 'Surface inspection passed without blocking findings.',
      );
    } catch (err) {
      setCorpusError(getErrorMessage(err));
    } finally {
      setInspectLoading(false);
    }
  };

  const handleDeidentify = async () => {
    setDeidentifyLoading(true);
    setCorpusNotice(null);
    setCorpusError(null);
    setDeidentifyResult(null);
    setCorpusReviewDecision(null);
    setCorpusImportResult(null);

    try {
      const response = await denialWorkflowApi.deidentifyCorpusDocument({
        document_text: corpusForm.visibleText.trim(),
        source_id: corpusForm.sourceId.trim() || 'SRC-UI-CANDIDATE',
        document_id: corpusForm.documentId.trim() || 'DOC-UI-CANDIDATE',
        document_role: corpusForm.documentRole,
      });
      setDeidentifyResult(response.data);
      setCorpusNotice(
        response.data.phi_scan_after.finding_count
          ? 'De-identification still has scanner findings.'
          : 'Machine de-identification has no scanner findings.',
      );
    } catch (err) {
      setCorpusError(getErrorMessage(err));
    } finally {
      setDeidentifyLoading(false);
    }
  };

  const handleImportApproved = async () => {
    if (!deidentifyResult || !importReadiness.ready) return;

    setImportLoading(true);
    setCorpusNotice(null);
    setCorpusError(null);
    setCorpusReviewDecision(null);
    setCorpusImportResult(null);

    try {
      const documentText = deidentifyResult.deidentified_text.trim();
      const documentId = corpusForm.documentId.trim() || deidentifyResult.document_id;
      const sourceId = corpusForm.sourceId.trim() || deidentifyResult.source_id;
      const residualRiskScore = Math.max(
        surfaceInspection?.residual_risk_score ?? 0,
        deidentifyResult.residual_risk_score,
      );
      const reviewedContextualRiskFindingCount = importReadiness.contextualRiskFindingCount;
      const reviewMethod = importReadiness.requiresExpertDetermination
        ? 'expert_determination'
        : 'privacy_review';
      const reviewedPhiStatus = corpusForm.phiStatus === 'no_phi' ? 'no_phi' : 'deidentified';
      const record: CorpusManifestRecord = {
        source_id: sourceId,
        document_id: documentId,
        pair_id: corpusForm.pairId.trim() || null,
        source_type: 'ui_reviewed_deidentified',
        document_role: corpusForm.documentRole,
        source_url_or_path: corpusForm.sourceFilename.trim() || `ui-reviewed://${documentId}`,
        checksum: await sha256Text(documentText),
        phi_status: reviewedPhiStatus,
        deidentification_status: importReadiness.requiresExpertDetermination
          ? 'expert_determination_required'
          : deidentifyResult.deidentification_status,
        license_status: corpusForm.licenseStatus.trim() || 'reviewed_allowed',
        review_status: importReadiness.requiresExpertDetermination
          ? 'expert_determination_required'
          : 'not_reviewed',
        residual_risk_score: residualRiskScore,
        training_eligible: false,
        split: 'none',
        micro_skill_ids: [],
        payer_type: corpusForm.payerType.trim() || null,
        denial_type: corpusForm.denialType.trim() || null,
        appeal_route: corpusForm.appealRoute.trim() || null,
        appeal_level: corpusForm.appealLevel.trim() || null,
        outcome: corpusForm.outcome.trim() || null,
        reviewer_id: null,
        review_timestamp: null,
        review_method: null,
        training_decision_note: null,
        review_findings: [],
        reviewed_phi_finding_count: 0,
        reviewed_contextual_risk_finding_count: 0,
        privacy_review_completed: false,
        license_review_completed: false,
        residual_risk_review_completed: false,
        expert_determination_completed: false,
      };

      const reviewResponse = await denialWorkflowApi.reviewCorpusDecision({
        record,
        reviewer_id: `ui_${currentUser.role}_privacy_reviewer`,
        review_method: reviewMethod,
        decision: 'approve_for_training',
        phi_status: reviewedPhiStatus,
        license_status: corpusForm.licenseStatus.trim() || 'reviewed_allowed',
        split: corpusForm.trainingSplit,
        micro_skill_ids: importReadiness.microSkillIds,
        residual_risk_score: residualRiskScore,
        privacy_review_completed: corpusForm.privacyReviewCompleted,
        license_review_completed: corpusForm.licenseReviewCompleted,
        residual_risk_review_completed: corpusForm.residualRiskReviewCompleted,
        expert_determination_completed: corpusForm.expertDeterminationCompleted,
        reviewed_phi_finding_count: deidentifyResult.phi_scan_after.finding_count,
        reviewed_contextual_risk_finding_count: reviewedContextualRiskFindingCount,
        review_findings: [
          'Surface inspection completed with metadata-only findings.',
          'Machine de-identification completed with no reviewed scanner findings.',
          reviewedContextualRiskFindingCount
            ? 'Contextual re-identification risk metadata reviewed without storing raw values.'
            : 'No contextual re-identification risk findings in reviewed metadata.',
        ],
        training_decision_note: 'Metadata-only UI approval request after surface inspection, machine de-identification, privacy review, license review, residual-risk review, and training split review.',
      });
      setCorpusReviewDecision(reviewResponse.data);

      if (!reviewResponse.data.approved_for_training) {
        setCorpusNotice('Review decision blocked corpus import.');
        return;
      }

      const response = await denialWorkflowApi.importApprovedCorpusDocument({
        record: reviewResponse.data.record,
        document_text: documentText,
      });
      setCorpusImportResult(response.data);
      setCorpusNotice(
        response.data.imported
          ? `Imported approved corpus source ${response.data.retrieval_source?.source_id ?? documentId}.`
          : 'Import was blocked by corpus validation.',
      );
      if (response.data.retrieval_source) {
        setStoredSources((current) => [response.data.retrieval_source as RetrievalSourceResponse, ...current].slice(0, 10));
      }
      await refreshStoredSourceGovernance();
      await onCorpusStatusRefresh();
    } catch (err) {
      setCorpusError(getErrorMessage(err));
    } finally {
      setImportLoading(false);
    }
  };

  return (
    <section className="bg-white p-6 shadow">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Corpus And Source Controls</h2>
          <p className="mt-1 text-sm text-gray-600">
            Import controls require privacy review, surface inspection, and de-identification gates.
          </p>
        </div>
        <Badge label="write role" className="bg-blue-50 text-blue-700 ring-blue-200" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <form onSubmit={handleCreateSource} className="space-y-4 rounded-md border border-gray-200 p-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Retrieval Source</h3>
            <p className="mt-1 text-sm text-gray-600">Stored sources are encrypted and gated by PHI declaration.</p>
          </div>
          {(sourceError || sourceNotice) && (
            <SafeHtml
              value={sourceError || sourceNotice}
              className={`rounded-md p-3 text-sm ${sourceError ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}
            />
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700">Title</label>
              <input
                type="text"
                value={sourceForm.title}
                onChange={(event) => setSourceForm((current) => ({ ...current, title: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Source Type</label>
              <input
                type="text"
                value={sourceForm.sourceType}
                onChange={(event) => setSourceForm((current) => ({ ...current, sourceType: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Payer Type</label>
              <input
                type="text"
                value={sourceForm.payerType}
                onChange={(event) => setSourceForm((current) => ({ ...current, payerType: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">License Status</label>
              <input
                type="text"
                value={sourceForm.licenseStatus}
                onChange={(event) => setSourceForm((current) => ({ ...current, licenseStatus: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Access Scope</label>
              <select
                value={sourceForm.accessScope}
                onChange={(event) => setSourceForm((current) => ({
                  ...current,
                  accessScope: event.target.value as RetrievalSourceAccessScope,
                }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              >
                {ACCESS_SCOPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Retention Until</label>
              <input
                type="datetime-local"
                value={sourceForm.retentionUntil}
                onChange={(event) => setSourceForm((current) => ({ ...current, retentionUntil: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Jurisdiction</label>
              <input
                type="text"
                value={sourceForm.jurisdiction}
                onChange={(event) => setSourceForm((current) => ({ ...current, jurisdiction: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Source URL</label>
              <input
                type="text"
                value={sourceForm.sourceUrl}
                onChange={(event) => setSourceForm((current) => ({ ...current, sourceUrl: event.target.value }))}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Section Label</label>
            <input
              type="text"
              value={sourceForm.sectionLabel}
              onChange={(event) => setSourceForm((current) => ({ ...current, sectionLabel: event.target.value }))}
              className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">PHI Status</label>
            <select
              value={sourceForm.phiStatus}
              onChange={(event) => setSourceForm((current) => ({ ...current, phiStatus: event.target.value as PhiStatus }))}
              className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
            >
              {PHI_STATUSES.map((status) => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Document Text</label>
            <textarea
              value={sourceForm.documentText}
              onChange={(event) => setSourceForm((current) => ({ ...current, documentText: event.target.value }))}
              rows={8}
              className="mt-1 block min-h-48 w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={sourceForm.privacyReviewCompleted}
                onChange={(event) => setSourceForm((current) => ({ ...current, privacyReviewCompleted: event.target.checked }))}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span>Privacy review completed</span>
            </label>
            <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={sourceForm.modelImprovementOptIn}
                disabled={!modelImprovementStatus?.ready}
                onChange={(event) => setSourceForm((current) => ({ ...current, modelImprovementOptIn: event.target.checked }))}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span>Model-improvement opt-in</span>
            </label>
          </div>
          {modelImprovementStatus && (
            <div className="rounded-md border border-gray-200 p-3 text-sm">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-medium text-gray-900">Model-improvement compliance</span>
                <Badge
                  label={modelImprovementStatus.ready ? 'ready' : 'blocked'}
                  className={modelImprovementStatus.ready ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-red-50 text-red-700 ring-red-200'}
                />
              </div>
              {modelImprovementStatus.blockers.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {modelImprovementStatus.blockers.map((blocker) => (
                    <Badge key={blocker} label={readableLabel(blocker)} className="bg-red-50 text-red-700 ring-red-200" />
                  ))}
                </div>
              )}
              {sourceForm.modelImprovementOptIn && (
                <div className="mt-3 space-y-3">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={sourceForm.modelImprovementLegalAttestation}
                        onChange={(event) => setSourceForm((current) => ({
                          ...current,
                          modelImprovementLegalAttestation: event.target.checked,
                        }))}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      <span>Legal approved</span>
                    </label>
                    <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={sourceForm.modelImprovementBaaAttestation}
                        onChange={(event) => setSourceForm((current) => ({
                          ...current,
                          modelImprovementBaaAttestation: event.target.checked,
                        }))}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      <span>BAA confirmed</span>
                    </label>
                    <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={sourceForm.modelImprovementConsentAttestation}
                        onChange={(event) => setSourceForm((current) => ({
                          ...current,
                          modelImprovementConsentAttestation: event.target.checked,
                        }))}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      <span>Consent confirmed</span>
                    </label>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Consent Notice Version</label>
                    <input
                      type="text"
                      value={sourceForm.modelImprovementConsentNoticeVersion}
                      onChange={(event) => setSourceForm((current) => ({
                        ...current,
                        modelImprovementConsentNoticeVersion: event.target.value,
                      }))}
                      placeholder={modelImprovementStatus.consent_notice_version ?? ''}
                      className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                    />
                  </div>
                </div>
              )}
            </div>
          )}
          <button
            type="submit"
            disabled={
              sourceLoading
              || sourceForm.documentText.trim().length < 20
              || !sourceForm.title.trim()
              || (
                sourceForm.modelImprovementOptIn
                && (
                  !sourceForm.modelImprovementLegalAttestation
                  || !sourceForm.modelImprovementBaaAttestation
                  || !sourceForm.modelImprovementConsentAttestation
                  || !sourceForm.modelImprovementConsentNoticeVersion.trim()
                )
              )
            }
            className="w-full rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sourceLoading ? 'Saving source...' : 'Save Retrieval Source'}
          </button>
        </form>

        <div className="space-y-4 rounded-md border border-gray-200 p-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Stored Sources</h3>
            <p className="mt-1 text-sm text-gray-600">Latest encrypted retrieval sources.</p>
          </div>
          {storedSourcesError && <div className="rounded-md bg-yellow-50 p-3 text-sm text-yellow-800">{storedSourcesError}</div>}
          {governanceSummary && (
            <div className="grid grid-cols-2 gap-3 text-sm lg:grid-cols-4">
              <div className="rounded-md bg-gray-50 p-3">
                <div className="text-xs font-medium uppercase text-gray-500">Active</div>
                <div className="mt-1 text-lg font-semibold text-gray-900">{governanceSummary.active_count}</div>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <div className="text-xs font-medium uppercase text-gray-500">Expired</div>
                <div className="mt-1 text-lg font-semibold text-red-700">{governanceSummary.expired_active_count}</div>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <div className="text-xs font-medium uppercase text-gray-500">Retired</div>
                <div className="mt-1 text-lg font-semibold text-gray-900">{governanceSummary.deleted_count}</div>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <div className="text-xs font-medium uppercase text-gray-500">No Expiry</div>
                <div className="mt-1 text-lg font-semibold text-gray-900">{governanceSummary.retained_without_expiration_count}</div>
              </div>
            </div>
          )}
          {governanceLoading && <div className="text-sm text-gray-500">Refreshing governance data...</div>}
          {currentUser.role === 'admin' && vectorReadiness && (
            <div className="rounded-md border border-gray-200 p-3 text-sm">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-medium text-gray-900">Vector readiness</span>
                <Badge
                  label={vectorReadiness.production_ready ? 'production ready' : 'blocked'}
                  className={vectorReadiness.production_ready ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-red-50 text-red-700 ring-red-200'}
                />
                <Badge
                  label={vectorReadiness.hash_fallback_in_use ? 'hash fallback' : 'semantic backend'}
                  className={vectorReadiness.hash_fallback_in_use ? 'bg-yellow-50 text-yellow-800 ring-yellow-200' : 'bg-blue-50 text-blue-700 ring-blue-200'}
                />
              </div>
              <div className="grid grid-cols-1 gap-2 text-xs text-gray-600 sm:grid-cols-2">
                <div>Embedding: {vectorReadiness.embedding_backend} / {vectorReadiness.embedding_model}</div>
                <div>Vector store: {vectorReadiness.vector_backend}</div>
                <div>Active chunks: {vectorReadiness.chunk_count}</div>
                <div>Reindex needed: {vectorReadiness.sources_requiring_reindex_count}</div>
              </div>
              {vectorReadiness.blockers.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {vectorReadiness.blockers.map((blocker) => (
                    <Badge key={blocker} label={readableLabel(blocker)} className="bg-red-50 text-red-700 ring-red-200" />
                  ))}
                </div>
              )}
            </div>
          )}
          {corpusReviewQueue && (
            <div className="rounded-md border border-gray-200 p-3 text-sm">
              <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h4 className="font-semibold text-gray-900">Manifest Review Queue</h4>
                  <p className="mt-1 text-xs text-gray-600">Metadata-only manifest records; text, paths, checksums, and matched values are redacted.</p>
                </div>
                <Badge
                  label={`${corpusReviewQueue.needs_review_count} need review`}
                  className={corpusReviewQueue.needs_review_count ? 'bg-yellow-50 text-yellow-800 ring-yellow-200' : 'bg-green-50 text-green-700 ring-green-200'}
                />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-500">Records</div>
                  <div className="mt-1 font-semibold text-gray-900">{corpusReviewQueue.record_count}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-500">Training Eligible</div>
                  <div className="mt-1 font-semibold text-gray-900">{corpusReviewQueue.training_eligible_count}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-500">Production Candidates</div>
                  <div className="mt-1 font-semibold text-gray-900">{corpusReviewQueue.production_candidate_count}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-500">Missing Pairs</div>
                  <div className="mt-1 font-semibold text-gray-900">{corpusReviewQueue.missing_pair_count}</div>
                </div>
              </div>
              {corpusReviewQueue.items.length === 0 ? (
                <p className="mt-3 text-xs text-gray-500">No manifest records returned.</p>
              ) : (
                <div className="mt-3 space-y-2">
                  {corpusReviewQueue.items.slice(0, 5).map((item) => (
                    <div key={item.document_id} className="rounded-md bg-gray-50 p-3">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="break-all font-medium text-gray-900">{item.document_id}</div>
                          <div className="mt-1 text-xs text-gray-500">
                            {readableLabel(item.document_role)} · {readableLabel(item.source_type)}
                          </div>
                        </div>
                        <Badge
                          label={item.ready_for_training_export ? 'export ready' : readableLabel(item.next_action)}
                          className={item.ready_for_training_export ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-yellow-50 text-yellow-800 ring-yellow-200'}
                        />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge label={item.phi_status} className="bg-blue-50 text-blue-700 ring-blue-200" />
                        <Badge label={readableLabel(item.review_status)} className="bg-gray-100 text-gray-700 ring-gray-200" />
                        <Badge label={`${item.micro_skill_count} skill(s)`} className="bg-purple-50 text-purple-700 ring-purple-200" />
                        <Badge
                          label={item.production_corpus_candidate ? 'production candidate' : 'nonproduction source'}
                          className={item.production_corpus_candidate ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-red-50 text-red-700 ring-red-200'}
                        />
                      </div>
                      {item.blockers.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {item.blockers.slice(0, 4).map((blocker) => (
                            <Badge key={`${item.document_id}-${blocker}`} label={readableLabel(blocker)} className="bg-red-50 text-red-700 ring-red-200" />
                          ))}
                          {item.blockers.length > 4 && (
                            <Badge label={`+${item.blockers.length - 4} more`} className="bg-red-50 text-red-700 ring-red-200" />
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {storedSources.length === 0 ? (
            <p className="text-sm text-gray-500">No stored sources loaded.</p>
          ) : (
            <div className="space-y-3">
              {storedSources.slice(0, 5).map((source) => (
                <div key={source.source_id} className="rounded-md bg-gray-50 p-3 text-sm">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <SafeHtml value={source.title} className="font-medium text-gray-900" />
                      <SafeHtml value={source.source_id} className="mt-1 text-xs text-gray-500" />
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleDeleteSource(source.source_id)}
                      disabled={deleteSourceId === source.source_id}
                      className="self-start rounded-md border border-red-200 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {deleteSourceId === source.source_id ? 'Retiring...' : 'Retire'}
                    </button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge label={source.source_type} className="bg-gray-100 text-gray-700 ring-gray-200" />
                    <Badge label={source.phi_status} className="bg-blue-50 text-blue-700 ring-blue-200" />
                    <Badge label={readableLabel(source.access_scope)} className="bg-purple-50 text-purple-700 ring-purple-200" />
                    <Badge label={`${source.chunk_count} chunk(s)`} className="bg-green-50 text-green-700 ring-green-200" />
                  </div>
                  <div className="mt-2 text-xs text-gray-500">
                    Retention: {formatDateTime(source.retention_until)}
                  </div>
                </div>
              ))}
            </div>
          )}
          {currentUser.role === 'admin' && auditDashboard && (
            <div className="rounded-md border border-gray-200 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-gray-900">Retrieval Audit Events</h4>
                <Badge label={`${auditDashboard.event_count} event(s)`} className="bg-blue-50 text-blue-700 ring-blue-200" />
              </div>
              {auditDashboard.events.length === 0 ? (
                <p className="text-sm text-gray-500">No retrieval audit events returned.</p>
              ) : (
                <div className="space-y-2">
                  {auditDashboard.events.slice(0, 5).map((event) => (
                    <div key={event.id} className="rounded-md bg-gray-50 p-2 text-xs text-gray-700">
                      <div className="font-medium text-gray-900">{readableLabel(event.action)}</div>
                      <div className="mt-1">{formatDateTime(event.timestamp)}</div>
                      <SafeHtml value={valueToText(event.details)} className="mt-1 break-words text-gray-500" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 rounded-md border border-gray-200 p-4">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Approved Corpus Import</h3>
            <p className="mt-1 text-sm text-gray-600">Candidate documents must pass surface and de-identification gates.</p>
          </div>
          <Badge
            label={importReadiness.ready ? 'ready to import' : 'review blocked'}
            className={importReadiness.ready ? 'bg-green-50 text-green-700 ring-green-200' : 'bg-red-50 text-red-700 ring-red-200'}
          />
        </div>
        {(corpusError || corpusNotice) && (
          <SafeHtml
            value={corpusError || corpusNotice}
            className={`mb-4 rounded-md p-3 text-sm ${corpusError ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}
          />
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">Source ID</label>
                <input
                  type="text"
                  value={corpusForm.sourceId}
                  onChange={(event) => updateCorpusField('sourceId', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Document ID</label>
                <input
                  type="text"
                  value={corpusForm.documentId}
                  onChange={(event) => updateCorpusField('documentId', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Pair ID</label>
                <input
                  type="text"
                  value={corpusForm.pairId}
                  onChange={(event) => updateCorpusField('pairId', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Document Role</label>
                <select
                  value={corpusForm.documentRole}
                  onChange={(event) => updateCorpusField('documentRole', event.target.value as CorpusDocumentRole)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                >
                  {CORPUS_DOCUMENT_ROLES.map((role) => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Source Filename</label>
                <input
                  type="text"
                  value={corpusForm.sourceFilename}
                  onChange={(event) => updateCorpusField('sourceFilename', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">MIME Type</label>
                <input
                  type="text"
                  value={corpusForm.sourceMimeType}
                  onChange={(event) => updateCorpusField('sourceMimeType', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Visible Text</label>
              <textarea
                value={corpusForm.visibleText}
                onChange={(event) => updateCorpusField('visibleText', event.target.value)}
                rows={8}
                className="mt-1 block min-h-48 w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">Hidden Text</label>
                <textarea
                  value={corpusForm.hiddenText}
                  onChange={(event) => updateCorpusField('hiddenText', event.target.value)}
                  rows={4}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">OCR Text</label>
                <textarea
                  value={corpusForm.ocrText}
                  onChange={(event) => updateCorpusField('ocrText', event.target.value)}
                  rows={4}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Header/Footer Text</label>
                <textarea
                  value={corpusForm.headerFooterText}
                  onChange={(event) => updateCorpusField('headerFooterText', event.target.value)}
                  rows={4}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Metadata</label>
                <textarea
                  value={corpusForm.metadataText}
                  onChange={(event) => updateCorpusField('metadataText', event.target.value)}
                  rows={4}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                  placeholder="title: Synthetic de-identified example"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Barcode/QR Text</label>
                <textarea
                  value={corpusForm.barcodeText}
                  onChange={(event) => updateCorpusField('barcodeText', event.target.value)}
                  rows={4}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Attachment Filenames</label>
                <textarea
                  value={corpusForm.attachmentFilenames}
                  onChange={(event) => updateCorpusField('attachmentFilenames', event.target.value)}
                  rows={4}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">PHI Status</label>
                <select
                  value={corpusForm.phiStatus}
                  onChange={(event) => updateCorpusField('phiStatus', event.target.value as PhiStatus)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                >
                  <option value="deidentified">De-identified</option>
                  <option value="no_phi">No PHI</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">License Status</label>
                <input
                  type="text"
                  value={corpusForm.licenseStatus}
                  onChange={(event) => updateCorpusField('licenseStatus', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Payer Type</label>
                <input
                  type="text"
                  value={corpusForm.payerType}
                  onChange={(event) => updateCorpusField('payerType', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Denial Type</label>
                <input
                  type="text"
                  value={corpusForm.denialType}
                  onChange={(event) => updateCorpusField('denialType', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Appeal Route</label>
                <input
                  type="text"
                  value={corpusForm.appealRoute}
                  onChange={(event) => updateCorpusField('appealRoute', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Appeal Level</label>
                <input
                  type="text"
                  value={corpusForm.appealLevel}
                  onChange={(event) => updateCorpusField('appealLevel', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Outcome</label>
                <input
                  type="text"
                  value={corpusForm.outcome}
                  onChange={(event) => updateCorpusField('outcome', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Micro Skills</label>
                <input
                  type="text"
                  value={corpusForm.microSkillIds}
                  onChange={(event) => updateCorpusField('microSkillIds', event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Training Split</label>
                <select
                  value={corpusForm.trainingSplit}
                  onChange={(event) => updateCorpusField('trainingSplit', event.target.value as typeof corpusForm.trainingSplit)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                >
                  {CORPUS_TRAINING_SPLITS.map((split) => (
                    <option key={split.value} value={split.value}>{split.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={corpusForm.privacyReviewCompleted}
                  onChange={(event) => updateCorpusField('privacyReviewCompleted', event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Raphael/privacy review completed</span>
              </label>
              <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={corpusForm.licenseReviewCompleted}
                  onChange={(event) => updateCorpusField('licenseReviewCompleted', event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>License review completed</span>
              </label>
              <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={corpusForm.residualRiskReviewCompleted}
                  onChange={(event) => updateCorpusField('residualRiskReviewCompleted', event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Residual-risk review completed</span>
              </label>
              <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={corpusForm.expertDeterminationCompleted}
                  onChange={(event) => updateCorpusField('expertDeterminationCompleted', event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Expert determination completed</span>
              </label>
              <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={corpusForm.trainingApproved}
                  onChange={(event) => updateCorpusField('trainingApproved', event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Request training approval</span>
              </label>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <button
                type="button"
                onClick={handleInspectSurfaces}
                disabled={inspectLoading || corpusForm.visibleText.trim().length < 20}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {inspectLoading ? 'Inspecting...' : 'Inspect Surfaces'}
              </button>
              <button
                type="button"
                onClick={handleDeidentify}
                disabled={deidentifyLoading || corpusForm.visibleText.trim().length < 20}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deidentifyLoading ? 'De-identifying...' : 'De-identify'}
              </button>
              <button
                type="button"
                onClick={handleImportApproved}
                disabled={importLoading || !importReadiness.ready}
                className="rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {importLoading ? 'Importing...' : 'Import Approved'}
              </button>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
              <div className="rounded-md bg-gray-50 p-3 text-sm">
                <div className="text-gray-500">Surfaces</div>
                <div className="mt-1 font-medium text-gray-900">
                  {surfaceInspection ? `${surfaceInspection.blocking_surface_count} blocking` : 'not inspected'}
                </div>
              </div>
              <div className="rounded-md bg-gray-50 p-3 text-sm">
                <div className="text-gray-500">De-ID Scan</div>
                <div className="mt-1 font-medium text-gray-900">
                  {deidentifyResult ? `${deidentifyResult.phi_scan_after.finding_count} finding(s)` : 'not run'}
                </div>
              </div>
              <div className="rounded-md bg-gray-50 p-3 text-sm">
                <div className="text-gray-500">Residual Risk</div>
                <div className="mt-1 font-medium text-gray-900">
                  {deidentifyResult ? deidentifyResult.residual_risk_score.toFixed(3) : 'N/A'}
                </div>
              </div>
              <div className="rounded-md bg-gray-50 p-3 text-sm">
                <div className="text-gray-500">Contextual Risk</div>
                <div className="mt-1 font-medium text-gray-900">
                  {surfaceInspection || deidentifyResult ? `${importReadiness.contextualRiskFindingCount} finding(s)` : 'N/A'}
                </div>
              </div>
            </div>
            {surfaceInspection && (
              <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <div className="font-medium text-gray-900">Surface results</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {surfaceInspection.surface_scans.map((surface) => (
                    <Badge
                      key={surface.surface}
                      label={`${readableLabel(surface.surface)}: ${surface.phi_scan.finding_count} PHI / ${surface.contextual_risk_findings.length} contextual`}
                      className={
                        surface.phi_scan.finding_count || surface.contextual_risk_findings.length
                          ? 'bg-red-50 text-red-700 ring-red-200'
                          : 'bg-green-50 text-green-700 ring-green-200'
                      }
                    />
                  ))}
                </div>
              </div>
            )}
            {deidentifyResult && (
              <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <div className="mb-2 font-medium text-gray-900">De-identified Text</div>
                <SafeHtml
                  value={deidentifyResult.deidentified_text}
                  preformatted
                  className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-white p-3 text-xs text-gray-800"
                />
              </div>
            )}
            {corpusReviewDecision && (
              <div
                className={`rounded-md p-3 text-sm ${
                  corpusReviewDecision.approved_for_training ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                }`}
              >
                <SafeHtml
                  value={
                    corpusReviewDecision.approved_for_training
                      ? 'Backend review decision approved the record for training import.'
                      : `Backend review decision blocked import: ${corpusReviewDecision.blockers.join(', ') || 'review not approved'}.`
                  }
                />
              </div>
            )}
            {corpusImportResult && (
              <div className={`rounded-md p-3 text-sm ${corpusImportResult.imported ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                <SafeHtml
                  value={
                    corpusImportResult.imported
                      ? `Imported ${corpusImportResult.retrieval_source?.source_id ?? corpusForm.documentId}.`
                      : `${corpusImportResult.validation.issues.length} validation issue(s) blocked import.`
                  }
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function DenialWorkflow({ currentUser }: DenialWorkflowProps) {
  const [documentText, setDocumentText] = useState('');
  const [documentType, setDocumentType] = useState('denial_letter');
  const [sourceDocumentId, setSourceDocumentId] = useState('denial_letter_1');
  const [sourceTitle, setSourceTitle] = useState('Uploaded denial source');
  const [phiStatus, setPhiStatus] = useState<PhiStatus>('contains_phi');
  const [useLlm, setUseLlm] = useState(false);
  const [workflow, setWorkflow] = useState<DenialWorkflowAnalysisResponse | null>(null);
  const [draftLetter, setDraftLetter] = useState('');
  const [sourceRegistry, setSourceRegistry] = useState<DenialWorkflowSourceRegistryItem[]>([]);
  const [sourceRegistryError, setSourceRegistryError] = useState<string | null>(null);
  const [studentModelStatus, setStudentModelStatus] = useState<DenialWorkflowStudentModelStatus | null>(null);
  const [studentModelError, setStudentModelError] = useState<string | null>(null);
  const [corpusStatus, setCorpusStatus] = useState<CorpusStatusResponse | null>(null);
  const [corpusStatusError, setCorpusStatusError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canManage = currentUser?.role === 'admin' || currentUser?.role === 'billing_staff';

  useEffect(() => {
    if (!canManage) return;
    let cancelled = false;

    const loadContext = async () => {
      const [registryResult, studentResult, corpusResult] = await Promise.allSettled([
        denialWorkflowApi.sourceRegistry(),
        denialWorkflowApi.studentModelStatus(),
        denialWorkflowApi.corpusStatus(),
      ]);
      if (cancelled) return;

      if (registryResult.status === 'fulfilled') {
        setSourceRegistry(registryResult.value.data.sources);
        setSourceRegistryError(null);
      } else {
        setSourceRegistryError('Source registry metadata is unavailable.');
      }

      if (studentResult.status === 'fulfilled') {
        setStudentModelStatus(studentResult.value.data);
        setStudentModelError(null);
      } else {
        setStudentModelError('Distilled student status is unavailable.');
      }

      if (corpusResult.status === 'fulfilled') {
        setCorpusStatus(corpusResult.value.data);
        setCorpusStatusError(null);
      } else {
        setCorpusStatusError('Corpus readiness status is unavailable.');
      }
    };

    loadContext();
    return () => {
      cancelled = true;
    };
  }, [canManage]);

  const workflowForReview = useMemo(() => {
    if (!workflow) return null;
    return { ...workflow, draft_appeal_letter: draftLetter };
  }, [draftLetter, workflow]);

  const refreshCorpusStatus = async () => {
    try {
      const response = await denialWorkflowApi.corpusStatus();
      setCorpusStatus(response.data);
      setCorpusStatusError(null);
    } catch {
      setCorpusStatusError('Corpus readiness status is unavailable.');
    }
  };

  const stats = useMemo(() => {
    if (!workflow) return null;
    return {
      facts: workflow.known_from_documents.length + workflow.inferred.length,
      openTasks: workflow.missing_needs_human_verification.length + workflow.provider_letter_request_checklist.length,
      blockers: workflow.quality_checks.filter((check) => check.status === 'blocker').length,
      citations: workflow.retrieval_citations.length + workflow.cited_rules.length,
      activePhases: workflow.workflow_phase_checklist.filter((phase) => phase.status !== 'not_started').length,
      phiFindings: workflow.phi_scan.finding_count,
    };
  }, [workflow]);

  const handleAnalyze = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage || !documentText.trim()) return;

    setAnalyzing(true);
    setError(null);
    setNotice(null);

    try {
      const response = await denialWorkflowApi.analyze({
        document_text: documentText.trim(),
        document_type: documentType,
        source_document_id: sourceDocumentId.trim() || 'denial_letter_1',
        source_title: sourceTitle.trim() || 'Uploaded denial source',
        phi_status: phiStatus,
        generate_draft: true,
        use_llm: useLlm,
      });
      setWorkflow(response.data);
      setDraftLetter(response.data.draft_appeal_letter || '');
      setNotice('Denial workflow generated for human review.');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleExport = async (format: ExportFormat) => {
    if (!workflowForReview) return;

    setExporting(format);
    setError(null);
    setNotice(null);

    try {
      const response = await denialWorkflowApi.exportPacket({
        workflow: workflowForReview,
        export_format: format,
        filename_prefix: 'claimguard-denial-workflow',
      });
      downloadExport(response.data.filename, response.data.content_type, response.data.encoding, response.data.content);
      setNotice(`${format.toUpperCase()} export generated.`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setExporting(null);
    }
  };

  if (!canManage) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">Denial Workflow</h1>
        <div className="bg-white p-6 shadow">
          <div className="rounded-md bg-gray-50 p-4 text-sm text-gray-700">
            Your role has read-only access.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Denial Workflow</h1>
          <p className="mt-2 max-w-3xl text-sm text-gray-600">
            Use synthetic, de-identified, or minimum-necessary content only. Outputs stay marked
            draft_for_human_review until staff verify facts, citations, deadlines, channels, and PHI scope.
          </p>
        </div>
        {workflow && (
          <Badge
            label={workflow.human_review_required ? 'Human review required' : 'Review status unknown'}
            className="bg-red-50 text-red-700 ring-red-200"
          />
        )}
      </div>

      {(error || notice) && (
        <SafeHtml
          value={error || notice}
          className={`mb-6 rounded-md border p-4 text-sm ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'}`}
        />
      )}

      {currentUser && (
        <div className="mb-6">
          <CorpusAdminPanel currentUser={currentUser} onCorpusStatusRefresh={refreshCorpusStatus} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <section className="bg-white p-6 shadow">
            <h2 className="mb-4 text-xl font-semibold text-gray-900">Analyze Case</h2>
            <form onSubmit={handleAnalyze} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Document Type</label>
                <select
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                >
                  {DOCUMENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Source Title</label>
                <input
                  type="text"
                  value={sourceTitle}
                  onChange={(event) => setSourceTitle(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Source Document ID</label>
                <input
                  type="text"
                  value={sourceDocumentId}
                  onChange={(event) => setSourceDocumentId(event.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">PHI Status</label>
                <select
                  value={phiStatus}
                  onChange={(event) => setPhiStatus(event.target.value as PhiStatus)}
                  className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                >
                  {PHI_STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Denial Text</label>
                <textarea
                  value={documentText}
                  onChange={(event) => setDocumentText(event.target.value)}
                  rows={13}
                  className="mt-1 block min-h-80 w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                  placeholder="Paste a de-identified denial letter, EOB, ERA, or payer notice excerpt..."
                />
              </div>

              <label className="flex items-start gap-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={useLlm}
                  onChange={(event) => setUseLlm(event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Use accepted distilled ClaimGuard student when the local MLX server is available</span>
              </label>

              <button
                type="submit"
                disabled={analyzing || documentText.trim().length < 20}
                className="w-full rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {analyzing ? 'Analyzing...' : 'Analyze Workflow'}
              </button>
            </form>
          </section>

          <StudentModelStatus status={studentModelStatus} error={studentModelError} />
          <CorpusReadinessPanel status={corpusStatus} error={corpusStatusError} />
          <SourceRegistry sources={sourceRegistry} error={sourceRegistryError} />
        </div>

        <div className="space-y-6 lg:col-span-2">
          {!workflow ? (
            <section className="bg-white p-6 shadow">
              <div className="flex min-h-96 items-center justify-center rounded-md border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
                {analyzing ? 'Generating denial workflow...' : 'No denial workflow generated'}
              </div>
            </section>
          ) : (
            <>
              <section className="bg-white p-6 shadow">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">Review Packet</h2>
                    <div className="mt-1 text-sm text-gray-500">
                      Generated {new Date(workflow.analyzed_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {EXPORT_FORMATS.map((format) => (
                      <button
                        key={format}
                        type="button"
                        onClick={() => handleExport(format)}
                        disabled={exporting !== null}
                        className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium uppercase text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {exporting === format ? 'Exporting...' : format}
                      </button>
                    ))}
                  </div>
                </div>

                {stats && (
                  <div className="grid grid-cols-2 gap-3 text-sm lg:grid-cols-6">
                    <div className="rounded-md bg-gray-50 p-3">
                      <div className="text-gray-500">Route</div>
                      <div className="mt-1 font-medium text-gray-900">{readableLabel(workflow.recommended_route)}</div>
                    </div>
                    <div className="rounded-md bg-gray-50 p-3">
                      <div className="text-gray-500">Confidence</div>
                      <div className="mt-1 font-medium capitalize text-gray-900">{workflow.route_confidence}</div>
                    </div>
                    <div className="rounded-md bg-gray-50 p-3">
                      <div className="text-gray-500">Facts</div>
                      <div className="mt-1 font-medium text-gray-900">{stats.facts}</div>
                    </div>
                    <div className="rounded-md bg-gray-50 p-3">
                      <div className="text-gray-500">Blockers</div>
                      <div className="mt-1 font-medium text-gray-900">{stats.blockers}</div>
                    </div>
                    <div className="rounded-md bg-gray-50 p-3">
                      <div className="text-gray-500">Active Phases</div>
                      <div className="mt-1 font-medium text-gray-900">{stats.activePhases}</div>
                    </div>
                    <div className="rounded-md bg-gray-50 p-3">
                      <div className="text-gray-500">PHI Findings</div>
                      <div className="mt-1 font-medium text-gray-900">{stats.phiFindings}</div>
                    </div>
                  </div>
                )}

                {workflow.warnings.length > 0 && (
                  <div className="mt-4 rounded-md border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
                    {workflow.warnings.map((warning, index) => (
                      <SafeHtml key={`${warning}-${index}`} value={warning} />
                    ))}
                  </div>
                )}
              </section>

              <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <div className="bg-white p-6 shadow">
                  <h2 className="mb-4 text-xl font-semibold text-gray-900">Case Summary</h2>
                  <div className="space-y-4 text-sm text-gray-700">
                    <SafeHtml value={workflow.case_summary} className="whitespace-pre-wrap" />
                    <div className="rounded-md bg-gray-50 p-4">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div>
                          <div className="text-gray-500">Payer</div>
                          <SafeHtml value={workflow.payer_name} emptyText="N/A" className="font-medium" />
                        </div>
                        <div>
                          <div className="text-gray-500">Payer Type</div>
                          <div className="font-medium">{readableLabel(workflow.payer_type)}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Plan Type</div>
                          <div className="font-medium">{readableLabel(workflow.plan_type)}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Denial Type</div>
                          <div className="font-medium">{readableLabel(workflow.denial_type)}</div>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-md bg-gray-50 p-4">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <div className="font-medium text-gray-900">PHI Scan</div>
                        <Badge
                          label={workflow.phi_scan.review_required ? 'review required' : 'no findings'}
                          className={phiStatusClass(workflow.phi_scan.review_required)}
                        />
                      </div>
                      <div>Findings: {workflow.phi_scan.finding_count}</div>
                      <div>Types: {workflow.phi_scan.finding_types.join(', ') || 'none'}</div>
                      <div>Values redacted: {workflow.phi_scan.values_redacted ? 'yes' : 'no'}</div>
                    </div>
                  </div>
                </div>

                <div className="bg-white p-6 shadow">
                  <h2 className="mb-4 text-xl font-semibold text-gray-900">Appeal Strategy</h2>
                  <SafeHtml value={workflow.appeal_strategy} className="whitespace-pre-wrap text-sm text-gray-700" />
                  <div className="mt-4 rounded-md bg-gray-50 p-4 text-sm text-gray-700">
                    <div className="font-medium text-gray-900">Submission Plan</div>
                    <div className="mt-2">Route: {readableLabel(workflow.submission_plan.route)}</div>
                    <div>Channel: <SafeHtml value={workflow.submission_plan.required_channel} inline /></div>
                    {workflow.submission_plan.proof_to_capture.length > 0 && (
                      <div className="mt-2">
                        Proof: <SafeHtml value={workflow.submission_plan.proof_to_capture.join(', ')} inline />
                      </div>
                    )}
                  </div>
                </div>
              </section>

              <section className="bg-white p-6 shadow">
                <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <h2 className="text-xl font-semibold text-gray-900">Draft Appeal Letter</h2>
                  <Badge label="draft_for_human_review" className="bg-red-50 text-red-700 ring-red-200" />
                </div>
                <textarea
                  value={draftLetter}
                  onChange={(event) => setDraftLetter(event.target.value)}
                  rows={18}
                  className="block min-h-96 w-full rounded-md border border-gray-300 p-3 text-sm leading-6 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                />
              </section>

              <section className="bg-white p-6 shadow">
                <h2 className="mb-4 text-xl font-semibold text-gray-900">Deadlines</h2>
                {workflow.deadline_table.length === 0 ? (
                  <p className="text-sm text-gray-500">No deadlines returned.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                        <tr>
                          <th className="px-3 py-2">Type</th>
                          <th className="px-3 py-2">Source Date</th>
                          <th className="px-3 py-2">Calculated</th>
                          <th className="px-3 py-2">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {workflow.deadline_table.map((deadline, index) => (
                          <tr key={`${deadline.deadline_type}-${index}`}>
                            <td className="px-3 py-3 font-medium text-gray-900">{readableLabel(deadline.deadline_type)}</td>
                            <td className="px-3 py-3 text-gray-700">{formatDate(deadline.source_stated_deadline)}</td>
                            <td className="px-3 py-3 text-gray-700">{formatDate(deadline.calculated_deadline)}</td>
                            <td className="px-3 py-3 text-gray-700">{readableLabel(deadline.verification_status)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <FactRows title="Known From Documents" facts={workflow.known_from_documents} />
                <FactRows title="Inferred" facts={workflow.inferred} />
              </div>

              <TaskList title="Missing Or Needs Verification" tasks={workflow.missing_needs_human_verification} />
              <TaskList title="Provider Letter Checklist" tasks={workflow.provider_letter_request_checklist} />
              <EvidenceGapList gaps={workflow.evidence_gaps} />

              <section className="bg-white p-6 shadow">
                <h2 className="mb-4 text-xl font-semibold text-gray-900">Denial Skill Phase Checklist</h2>
                {workflow.workflow_phase_checklist.length === 0 ? (
                  <p className="text-sm text-gray-500">No phase checklist returned.</p>
                ) : (
                  <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                    {workflow.workflow_phase_checklist.map((phase) => (
                      <div key={phase.phase_id} className="rounded-md border border-gray-200 p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              <SafeHtml value={`${phase.phase_id} ${phase.phase_name}`} />
                            </div>
                            <SafeHtml value={phase.output_artifact} className="mt-1 text-sm text-gray-600" />
                          </div>
                          <Badge label={readableLabel(phase.status)} className={phaseStatusClass(phase.status)} />
                        </div>
                        <div className="mt-3 text-xs text-gray-500">Owner: <SafeHtml value={phase.owner} inline /></div>
                        {phase.related_tasks.length > 0 && (
                          <div className="mt-2 text-xs text-gray-600">
                            <SafeHtml value={phase.related_tasks.slice(0, 2).join(' | ')} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <div className="bg-white p-6 shadow">
                  <h2 className="mb-4 text-xl font-semibold text-gray-900">Attachment Index</h2>
                  {workflow.attachment_index.length === 0 ? (
                    <p className="text-sm text-gray-500">No attachments returned.</p>
                  ) : (
                    <div className="space-y-3">
                      {workflow.attachment_index.map((attachment, index) => (
                        <div key={`${attachment.label}-${index}`} className="border-b border-gray-100 pb-3 last:border-b-0 last:pb-0">
                          <SafeHtml value={attachment.label} className="text-sm font-medium text-gray-900" />
                          <SafeHtml value={attachment.description} className="mt-1 text-sm text-gray-700" />
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Badge label={readableLabel(attachment.source_status)} className={sourceStatusClass(attachment.source_status)} />
                            <Badge
                              label={attachment.required_before_submission ? 'required' : 'optional'}
                              className="bg-gray-50 text-gray-700 ring-gray-200"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-white p-6 shadow">
                  <h2 className="mb-4 text-xl font-semibold text-gray-900">Quality Checks</h2>
                  {workflow.quality_checks.length === 0 ? (
                    <p className="text-sm text-gray-500">No quality checks returned.</p>
                  ) : (
                    <div className="space-y-3">
                      {workflow.quality_checks.map((check, index) => (
                        <div key={`${check.check}-${index}`} className={`rounded-md p-3 text-sm ${qualityClass(check.status)}`}>
                          <SafeHtml value={`${readableLabel(check.status)}: ${check.check}`} className="font-medium" />
                          <SafeHtml value={check.details} className="mt-1" />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
