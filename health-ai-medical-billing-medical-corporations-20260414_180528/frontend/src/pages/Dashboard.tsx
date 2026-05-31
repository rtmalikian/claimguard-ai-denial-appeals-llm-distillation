import { useEffect, useState } from 'react';
import { analyticsApi, claimsApi, ClaimResponse, ClaimDocument } from '../api/client';
import { Link } from 'react-router-dom';
import SafeHtml from '../components/common/SafeHtml';

interface Summary {
  total_claims: number;
  pending_claims: number;
  processed_claims: number;
  predicted_denial_rate: number;
  claims_by_status: { status: string; count: number; percentage: number }[];
  top_denial_patterns: { pattern: string; count: number; percentage: number }[];
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [recentClaims, setRecentClaims] = useState<ClaimResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ClaimResponse[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<ClaimResponse | null>(null);
  const [showSearch, setShowSearch] = useState(false);
  const [showDocument, setShowDocument] = useState(false);
  const [documentContent, setDocumentContent] = useState<ClaimDocument | null>(null);
  const [docLoading, setDocLoading] = useState(false);

  const fetchData = () => {
    Promise.all([
      analyticsApi.getSummary(),
      claimsApi.listClaims(0, 50),
    ])
      .then(([summaryRes, claimsRes]) => {
        setSummary(summaryRes.data);
        setRecentClaims(claimsRes.data.slice(0, 10));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const fetchClaimDocument = async (claimId: number) => {
    setDocLoading(true);
    try {
      const res = await claimsApi.getClaimDocument(claimId);
      setDocumentContent(res.data);
      setShowDocument(true);
    } catch (err) {
      console.error(err);
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(detail || 'Document is not available for this claim');
    }
    setDocLoading(false);
  };

  const searchClaims = async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      setShowSearch(false);
      return;
    }
    try {
      const res = await claimsApi.listClaims(0, 100);
      const q = query.toLowerCase();
      const results = res.data.filter((c: ClaimResponse) => 
        c.id.toString().includes(q) ||
        c.status.toLowerCase().includes(q) ||
        JSON.stringify(c.claim_data).toLowerCase().includes(q) ||
        (c.diagnosis_codes || []).some((d: string) => d.toLowerCase().includes(q)) ||
        (c.procedure_codes || []).some((p: string) => p.toLowerCase().includes(q))
      );
      setSearchResults(results);
      setShowSearch(true);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const severityColor = (s: string) => {
    if (s === 'high') return 'text-red-600 bg-red-50';
    if (s === 'medium') return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const documentButtonLabel = (claim: ClaimResponse) => {
    const governance = claim.document_governance;
    if (!governance) return 'No Document Available';
    if (governance.is_retired) return 'Document Retired';
    if (governance.is_retention_expired) return 'Retention Expired';
    if (!governance.can_view_document) return 'Document Restricted';
    return docLoading ? 'Loading...' : 'View Original Document';
  };

  const documentStatusClass = (claim: ClaimResponse) => {
    const governance = claim.document_governance;
    if (!governance) return 'bg-gray-100 text-gray-700';
    if (governance.is_retired || governance.is_retention_expired) return 'bg-red-50 text-red-700';
    if (!governance.can_view_document) return 'bg-yellow-50 text-yellow-700';
    return 'bg-green-50 text-green-700';
  };

  const claimNeedsHumanReview = (claim: ClaimResponse) => (
    claim.human_review_required || (claim.denial_prediction || 0) > 0.5
  );

  const reviewReasonLabel = (reason: string) => reason.replace(/_/g, ' ');

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <Link to="/claims" className="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700">
          Analyze New Claim
        </Link>
      </div>
      
      <div className="mb-6">
        <input
          type="text"
          placeholder="Search claims by ID, status, diagnosis, procedure codes..."
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); searchClaims(e.target.value); }}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-primary-500 focus:border-primary-500"
        />
        {showSearch && searchResults.length > 0 && (
          <div className="mt-2 bg-white rounded-lg shadow-lg border max-h-64 overflow-y-auto">
            {searchResults.map((claim) => (
              <div
                key={claim.id}
                onClick={() => { setSelectedClaim(claim); setShowSearch(false); setSearchQuery(''); }}
                className="px-4 py-3 border-b last:border-0 hover:bg-gray-50 cursor-pointer"
              >
                <div className="flex justify-between">
                  <span className="font-medium">Claim #{claim.id}</span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    claim.status === 'analyzed' ? 'bg-blue-100 text-blue-800' :
                    claim.status === 'submitted' ? 'bg-yellow-100 text-yellow-800' :
                    claim.status === 'denied' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>{claim.status}</span>
                </div>
                <div className="text-sm text-gray-500">
                  {claim.claim_data?.description || 'No description'} | ${claim.claim_data?.amount || 0}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Total Claims</div>
          <div className="text-3xl font-bold text-primary-600">{summary?.total_claims || 0}</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Pending</div>
          <div className="text-3xl font-bold text-yellow-600">{summary?.pending_claims || 0}</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Processed</div>
          <div className="text-3xl font-bold text-green-600">{summary?.processed_claims || 0}</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm text-gray-500">Predicted Denial Rate</div>
          <div className="text-3xl font-bold text-red-600">{((summary?.predicted_denial_rate || 0) * 100).toFixed(1)}%</div>
        </div>
      </div>

      {selectedClaim && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-6">
                <h2 className="text-2xl font-bold">Claim #{selectedClaim.id}</h2>
                <button onClick={() => setSelectedClaim(null)} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
              </div>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-gray-500">Status</div>
                    <span className={`px-3 py-1 rounded text-sm font-medium ${
                      selectedClaim.status === 'analyzed' ? 'bg-blue-100 text-blue-800' :
                      selectedClaim.status === 'submitted' ? 'bg-yellow-100 text-yellow-800' :
                      selectedClaim.status === 'denied' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>{selectedClaim.status}</span>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">Denial Risk</div>
                    <div className={`text-xl font-bold ${
                      (selectedClaim.denial_prediction || 0) > 0.5 ? 'text-red-600' :
                      (selectedClaim.denial_prediction || 0) > 0.3 ? 'text-yellow-600' : 'text-green-600'
                    }`}>
                      {((selectedClaim.denial_prediction || 0) * 100).toFixed(0)}%
                      <span className="text-sm font-normal text-gray-500 ml-2">
                        ({((selectedClaim.denial_confidence || 0) * 100).toFixed(0)}% confidence)
                      </span>
                    </div>
                    {claimNeedsHumanReview(selectedClaim) && (
                      <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">
                        <div className="font-semibold">Human review required</div>
                        <div>Route to billing review before the next payer action.</div>
                        {selectedClaim.human_review_reasons?.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {selectedClaim.human_review_reasons.map((reason) => (
                              <span key={reason} className="rounded bg-white px-2 py-0.5 font-medium">
                                {reviewReasonLabel(reason)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-sm text-gray-500">Claim Details</div>
                  <div className="bg-gray-50 p-3 rounded">
                    <p><strong>Service Date:</strong> {selectedClaim.claim_data?.service_date || 'N/A'}</p>
                    <p><strong>Amount:</strong> ${selectedClaim.claim_data?.amount || 0}</p>
                    <p><strong>Description:</strong> {selectedClaim.claim_data?.description || 'N/A'}</p>
                  </div>
                  <button
                    onClick={() => fetchClaimDocument(selectedClaim.id)}
                    disabled={docLoading || !selectedClaim.document_available}
                    className="mt-2 w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {documentButtonLabel(selectedClaim)}
                  </button>
                  {selectedClaim.document_governance && (
                    <div className={`mt-2 rounded p-2 text-xs ${documentStatusClass(selectedClaim)}`}>
                      Scope: {selectedClaim.document_governance.access_scope.replace(/_/g, ' ')}
                      {selectedClaim.document_governance.retention_until && (
                        <span> | Retains until: {new Date(selectedClaim.document_governance.retention_until).toLocaleDateString()}</span>
                      )}
                      {selectedClaim.document_governance.deletion_reason && (
                        <span> | Reason: <SafeHtml value={selectedClaim.document_governance.deletion_reason} inline /></span>
                      )}
                    </div>
                  )}
                </div>

                {selectedClaim.claim_data?.ai_analysis && (
                  <div>
                    <div className="text-sm text-gray-500">AI Analysis</div>
                    <SafeHtml value={selectedClaim.claim_data.ai_analysis} className="bg-blue-50 p-3 rounded text-sm" />
                  </div>
                )}

                {selectedClaim.claim_data?.appeal_strategy && (
                  <div>
                    <div className="text-sm text-gray-500">Appeal Strategy</div>
                    <SafeHtml value={selectedClaim.claim_data.appeal_strategy} className="bg-green-50 p-3 rounded text-sm" />
                  </div>
                )}

                {((selectedClaim.diagnosis_codes?.length ?? 0) > 0 || (selectedClaim.procedure_codes?.length ?? 0) > 0) && (
                  <div className="grid grid-cols-2 gap-4">
                    {(selectedClaim.diagnosis_codes?.length ?? 0) > 0 && (
                      <div>
                        <div className="text-sm text-gray-500">Diagnosis Codes</div>
                        <div className="flex flex-wrap gap-2 mt-1">
                          {selectedClaim.diagnosis_codes?.map((code, i) => (
                            <SafeHtml key={i} value={code} inline className="bg-red-100 text-red-800 px-2 py-1 rounded text-sm font-mono" />
                          ))}
                        </div>
                      </div>
                    )}
                    {(selectedClaim.procedure_codes?.length ?? 0) > 0 && (
                      <div>
                        <div className="text-sm text-gray-500">Procedure Codes</div>
                        <div className="flex flex-wrap gap-2 mt-1">
                          {selectedClaim.procedure_codes?.map((code, i) => (
                            <SafeHtml key={i} value={code} inline className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-mono" />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {(selectedClaim.denial_reasons?.length ?? 0) > 0 && (
                  <div>
                    <div className="text-sm text-gray-500 mb-2">Denial Reasons</div>
                    {selectedClaim.denial_reasons?.map((r, i) => (
                      <div key={i} className={`p-3 rounded mb-2 ${severityColor(r.severity)}`}>
                        <SafeHtml value={r.reason} className="font-medium" />
                        {r.code && <div className="text-sm">Code: <SafeHtml value={r.code} inline /></div>}
                      </div>
                    ))}
                  </div>
                )}

                {(selectedClaim.recommendations?.length ?? 0) > 0 && (
                  <div>
                    <div className="text-sm text-gray-500 mb-2">Recommendations</div>
                    {selectedClaim.recommendations?.map((r, i) => (
                      <div key={i} className="border-l-4 border-primary-500 pl-4 mb-2">
                        <SafeHtml value={r.action} className="font-medium" />
                        <SafeHtml value={r.description} className="text-sm text-gray-600" />
                      </div>
                    ))}
                  </div>
                )}

                <div className="text-sm text-gray-500 border-t pt-4">
                  Created: {new Date(selectedClaim.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Claims by Status</h2>
          {summary?.claims_by_status.map(s => (
            <div key={s.status} className="flex justify-between py-2 border-b">
              <span className="capitalize">{s.status}</span>
              <span>{s.count} ({s.percentage}%)</span>
            </div>
          ))}
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Top Denial Patterns</h2>
          {summary?.top_denial_patterns.map((p, i) => (
            <div key={i} className="flex justify-between py-2 border-b">
              <span>{p.pattern}</span>
              <span>{p.percentage}% denial rate</span>
            </div>
          ))}
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Recent Claims</h2>
          {recentClaims.length === 0 ? (
            <p className="text-gray-500 text-sm">No claims yet</p>
          ) : (
            recentClaims.map(claim => (
              <div
                key={claim.id}
                onClick={() => setSelectedClaim(claim)}
                className="py-3 border-b last:border-0 cursor-pointer hover:bg-gray-50"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-sm font-medium">Claim #{claim.id}</span>
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                      claim.status === 'analyzed' ? 'bg-blue-100 text-blue-800' :
                      claim.status === 'submitted' ? 'bg-yellow-100 text-yellow-800' :
                      claim.status === 'denied' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {claim.status}
                    </span>
                  </div>
                  {claim.denial_prediction != null && (
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-bold ${
                        claim.denial_prediction > 0.5 ? 'text-red-600' :
                        claim.denial_prediction > 0.3 ? 'text-yellow-600' : 'text-green-600'
                      }`}>
                        {(claim.denial_prediction * 100).toFixed(0)}%
                      </span>
                      {claimNeedsHumanReview(claim) && (
                        <span className="rounded bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                          Review
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {new Date(claim.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {showDocument && documentContent && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-[60] p-4">
          <div className="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-gray-50">
              <div>
                <h3 className="text-lg font-bold">Original Document</h3>
                {documentContent.filename && (
                  <SafeHtml value={documentContent.filename} className="text-sm text-gray-500" />
                )}
                <p className="text-xs text-gray-500">
                  Scope: {documentContent.governance.access_scope.replace(/_/g, ' ')}
                  {documentContent.governance.retention_until && (
                    <span> | Retains until: {new Date(documentContent.governance.retention_until).toLocaleDateString()}</span>
                  )}
                </p>
              </div>
              <button onClick={() => { setShowDocument(false); setDocumentContent(null); }}
                className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <SafeHtml
                value={documentContent.document_text}
                preformatted
                className="whitespace-pre-wrap text-sm font-mono bg-gray-100 p-4 rounded-lg border max-h-[60vh] overflow-y-auto"
              />
            </div>
            <div className="p-4 border-t flex justify-end gap-2">
              <button onClick={() => {
                const blob = new Blob([documentContent.document_text], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = documentContent.filename || `claim-${documentContent.claim_id}.txt`;
                a.click();
                URL.revokeObjectURL(url);
              }}
                className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700">
                Download
              </button>
              <button onClick={() => { setShowDocument(false); setDocumentContent(null); }}
                className="bg-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-400">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
