import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { appealsApi, claimsApi } from '../api/client';
import type { AppealGenerateResponse, AuthUser, ClaimResponse } from '../api/client';
import SafeHtml from '../components/common/SafeHtml';

interface AppealsProps {
  currentUser: AuthUser | null;
}

const getErrorMessage = (err: unknown) => {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return 'Request failed';
};

const formatAmount = (value: string | number | boolean | null | undefined) => {
  if (typeof value === 'number') return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      return `$${parsed.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
  }
  return 'N/A';
};

const claimLabel = (claim: ClaimResponse) => {
  const amount = formatAmount(claim.claim_data?.amount);
  const status = claim.status || 'unknown';
  return `Claim #${claim.id} - ${status} - ${amount}`;
};

const topDenialReason = (claim: ClaimResponse) => {
  const reason = claim.denial_reasons?.[0];
  if (!reason) return 'N/A';
  return reason.code ? `${reason.code}: ${reason.reason}` : reason.reason;
};

export default function Appeals({ currentUser }: AppealsProps) {
  const [claims, setClaims] = useState<ClaimResponse[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState('');
  const [appealReason, setAppealReason] = useState('');
  const [additionalContext, setAdditionalContext] = useState('');
  const [result, setResult] = useState<AppealGenerateResponse | null>(null);
  const [loadingClaims, setLoadingClaims] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canGenerate = currentUser?.role === 'admin' || currentUser?.role === 'billing_staff';

  const selectedClaim = useMemo(() => {
    const id = Number(selectedClaimId);
    return claims.find((claim) => claim.id === id) || null;
  }, [claims, selectedClaimId]);

  useEffect(() => {
    const loadClaims = async () => {
      setLoadingClaims(true);
      setError(null);
      try {
        const res = await claimsApi.listClaims(0, 100);
        setClaims(res.data);
        if (res.data.length > 0) {
          setSelectedClaimId(String(res.data[0].id));
        }
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoadingClaims(false);
      }
    };

    loadClaims();
  }, []);

  const handleGenerate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canGenerate || !selectedClaimId || !appealReason.trim()) return;

    setGenerating(true);
    setError(null);
    setNotice(null);
    setResult(null);

    try {
      const res = await appealsApi.generate(
        Number(selectedClaimId),
        appealReason.trim(),
        additionalContext.trim() || undefined
      );
      setResult(res.data);
      setNotice(`Appeal letter generated for claim #${res.data.claim_id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!result?.appeal_letter) return;

    try {
      await navigator.clipboard.writeText(result.appeal_letter);
      setNotice('Appeal letter copied');
      setError(null);
    } catch {
      setError('Unable to copy appeal letter');
    }
  };

  const handleDownload = () => {
    if (!result?.appeal_letter) return;

    const fileContent = [
      `Claim ID: ${result.claim_id}`,
      `Generated: ${new Date(result.generated_at).toLocaleString()}`,
      '',
      result.appeal_letter,
      '',
      'Supporting Evidence:',
      ...result.supporting_evidence.map((item) => `- ${item}`),
    ].join('\n');

    const blob = new Blob([fileContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `appeal-claim-${result.claim_id}.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  if (!canGenerate) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">Appeals</h1>
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
      <h1 className="mb-8 text-3xl font-bold text-gray-900">Appeals</h1>

      {(error || notice) && (
        <div className={`mb-6 rounded-md border p-4 text-sm ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'}`}>
          <SafeHtml value={error || notice} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="bg-white p-6 shadow lg:col-span-1">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">Generate Letter</h2>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Claim</label>
              <select
                value={selectedClaimId}
                onChange={(event) => {
                  setSelectedClaimId(event.target.value);
                  setResult(null);
                  setNotice(null);
                }}
                disabled={loadingClaims || claims.length === 0}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500 disabled:bg-gray-100"
              >
                {loadingClaims ? (
                  <option value="">Loading claims...</option>
                ) : claims.length === 0 ? (
                  <option value="">No claims available</option>
                ) : (
                  claims.map((claim) => (
                    <option key={claim.id} value={claim.id}>
                      {claimLabel(claim)}
                    </option>
                  ))
                )}
              </select>
            </div>

            {selectedClaim && (
              <div className="rounded-md bg-gray-50 p-4 text-sm text-gray-700">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-gray-500">Status</div>
                    <div className="font-medium capitalize">{selectedClaim.status}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Patient ID</div>
                    <div className="font-medium">#{selectedClaim.patient_id}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Amount</div>
                    <div className="font-medium">{formatAmount(selectedClaim.claim_data?.amount)}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Denial Risk</div>
                    <div className="font-medium">
                      {selectedClaim.denial_prediction == null ? 'N/A' : `${(selectedClaim.denial_prediction * 100).toFixed(0)}%`}
                    </div>
                  </div>
                </div>
                <div className="mt-3">
                  <div className="text-gray-500">Top Denial Reason</div>
                  <SafeHtml value={topDenialReason(selectedClaim)} className="font-medium" />
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700">Appeal Reason</label>
              <textarea
                value={appealReason}
                onChange={(event) => setAppealReason(event.target.value)}
                rows={5}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                placeholder="Service was medically necessary..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Additional Context</label>
              <textarea
                value={additionalContext}
                onChange={(event) => setAdditionalContext(event.target.value)}
                rows={4}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                placeholder="Prior authorization, coding notes, or documentation details..."
              />
            </div>

            <button
              type="submit"
              disabled={generating || loadingClaims || !selectedClaimId || !appealReason.trim()}
              className="w-full rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generating ? 'Generating...' : 'Generate Appeal'}
            </button>
          </form>
        </section>

        <section className="bg-white p-6 shadow lg:col-span-2">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-xl font-semibold text-gray-900">Preview</h2>
            {result && (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Copy
                </button>
                <button
                  type="button"
                  onClick={handleDownload}
                  className="rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700"
                >
                  Download
                </button>
              </div>
            )}
          </div>

          {!result ? (
            <div className="flex min-h-96 items-center justify-center rounded-md border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
              {generating ? 'Generating appeal letter...' : 'No appeal generated'}
            </div>
          ) : (
            <div className="space-y-6">
              <div className="rounded-md bg-gray-50 p-4 text-sm text-gray-700">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <div className="text-gray-500">Claim</div>
                    <div className="font-medium">#{result.claim_id}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Generated</div>
                    <div className="font-medium">{new Date(result.generated_at).toLocaleString()}</div>
                  </div>
                </div>
              </div>

              <SafeHtml
                value={result.appeal_letter}
                preformatted
                className="min-h-96 whitespace-pre-wrap rounded-md border border-gray-200 bg-white p-4 text-sm leading-6 text-gray-900"
              />

              {result.supporting_evidence.length > 0 && (
                <div>
                  <h3 className="mb-3 text-lg font-semibold text-gray-900">Supporting Evidence</h3>
                  <ul className="space-y-2">
                    {result.supporting_evidence.map((item, index) => (
                      <li key={`${item}-${index}`} className="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-800">
                        <SafeHtml value={item} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
