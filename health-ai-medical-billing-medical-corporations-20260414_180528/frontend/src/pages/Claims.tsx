import { useState } from 'react';
import { claimsApi, ClaimData, ClaimPredictionResponse, DenialReason, Recommendation, DocumentAnalysisResponse } from '../api/client';
import SafeHtml from '../components/common/SafeHtml';

export default function Claims() {
  const [activeTab, setActiveTab] = useState<'claim' | 'document'>('document');
  const [formData, setFormData] = useState<ClaimData>({
    patient_id: 1,
    provider_id: 1,
    claim_data: { service_date: '', amount: 0, description: '' },
    diagnosis_codes: [],
    procedure_codes: []
  });
  const [documentText, setDocumentText] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [result, setResult] = useState<ClaimPredictionResponse | null>(null);
  const [docResult, setDocResult] = useState<DocumentAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await claimsApi.predict(formData);
      setResult(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const handleDocumentAnalyze = async () => {
    if (!documentText.trim()) return;
    setLoading(true);
    try {
      const res = await claimsApi.analyzeDocument({
        document_text: documentText,
        document_type: 'denial_letter'
      });
      setDocResult(res.data);
      if (res.data.claim_id) {
        alert(`Claim #${res.data.claim_id} saved! View it in the Dashboard.`);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to analyze document');
    }
    setLoading(false);
  };

  const handleFileUpload = async () => {
    if (!uploadedFile) return;
    setLoading(true);
    try {
      const res = await claimsApi.uploadDocument(uploadedFile);
      setDocResult(res.data);
      if (res.data.claim_id) {
        alert(`Claim #${res.data.claim_id} saved! View it in the Dashboard.`);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to upload document');
    }
    setLoading(false);
  };

  const severityColor = (s: string) => {
    if (s === 'high') return 'text-red-600 bg-red-50';
    if (s === 'medium') return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const reviewReasonLabel = (reason: string) => reason.replace(/_/g, ' ');

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Claim Analysis</h1>
      
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button onClick={() => setActiveTab('document')} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'document' ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            Analyze Document
          </button>
          <button onClick={() => setActiveTab('claim')} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'claim' ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            Predict Claim Denial
          </button>
        </nav>
      </div>

      {activeTab === 'document' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Upload Denial Letter</h2>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">Upload Denial Letter (PDF, TXT, JPG, PNG, GIF, WebP, BMP)</label>
              <input type="file" accept=".pdf,.txt,.text,.denial,.jpg,.jpeg,.png,.gif,.webp,.bmp" onChange={e => setUploadedFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100" />
              {uploadedFile && (
                <button onClick={handleFileUpload} disabled={loading}
                  className="mt-2 w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 disabled:opacity-50">
                  {loading ? 'Analyzing...' : 'Analyze File'}
                </button>
              )}
            </div>

            <div className="border-t pt-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">Or paste denial letter text</label>
              <textarea value={documentText} onChange={e => setDocumentText(e.target.value)} rows={8}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" 
                placeholder="Paste the content of your denial letter here..." />
              <button onClick={handleDocumentAnalyze} disabled={loading || !documentText.trim()}
                className="mt-3 w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 disabled:opacity-50">
                {loading ? 'Analyzing...' : 'Analyze Text'}
              </button>
            </div>
          </div>

          {docResult && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-semibold mb-4">Extracted Information</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div><span className="text-gray-500">Payer:</span> <SafeHtml value={docResult.payer_name} emptyText="N/A" inline /></div>
                  <div><span className="text-gray-500">Patient:</span> <SafeHtml value={docResult.patient_name} emptyText="N/A" inline /></div>
                  <div><span className="text-gray-500">Policy #:</span> <SafeHtml value={docResult.policy_number} emptyText="N/A" inline /></div>
                  <div><span className="text-gray-500">Claim Amount:</span> {docResult.claim_amount ? `$${docResult.claim_amount.toFixed(2)}` : 'N/A'}</div>
                  <div><span className="text-gray-500">Service Date:</span> <SafeHtml value={docResult.service_date} emptyText="N/A" inline /></div>
                  <div><span className="text-gray-500">Denial Code:</span> <SafeHtml value={docResult.denial_code} emptyText="N/A" inline className="font-mono bg-red-100 px-2 py-0.5 rounded" /></div>
                </div>
                {docResult.extracted_codes.length > 0 && (
                  <div className="mt-3">
                    <span className="text-gray-500 text-sm">CPT/HCPCS Codes:</span>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {docResult.extracted_codes.map((code, i) => (
                        <SafeHtml key={i} value={code} inline className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-mono" />
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {docResult.document_surface_inspection && (
                <div className={`p-6 rounded-lg border ${
                  docResult.document_surface_inspection.blocking_surface_count
                    ? 'bg-red-50 border-red-200'
                    : 'bg-green-50 border-green-200'
                }`}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className={`text-lg font-semibold ${
                        docResult.document_surface_inspection.blocking_surface_count
                          ? 'text-red-800'
                          : 'text-green-800'
                      }`}>
                        Document Surface Inspection
                      </h3>
                      <p className={`mt-1 text-sm ${
                        docResult.document_surface_inspection.blocking_surface_count
                          ? 'text-red-700'
                          : 'text-green-700'
                      }`}>
                        {docResult.document_surface_inspection.blocking_surface_count} blocking surface(s),
                        {' '}
                        {docResult.document_surface_inspection.residual_risk_score.toFixed(3)} residual risk.
                      </p>
                    </div>
                    <span className={`rounded px-2 py-1 text-xs font-medium ${
                      docResult.document_surface_inspection.blocking_surface_count
                        ? 'bg-red-100 text-red-800'
                        : 'bg-green-100 text-green-800'
                    }`}>
                      {docResult.document_surface_inspection.deidentification_status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {docResult.document_surface_inspection.surface_scans.map((surface) => (
                      <span
                        key={surface.surface}
                        className={`rounded px-2 py-1 text-xs font-medium ${
                          surface.phi_scan.finding_count
                            ? 'bg-red-100 text-red-800'
                            : 'bg-green-100 text-green-800'
                        }`}
                      >
                        {surface.surface.replace(/_/g, ' ')}: {surface.phi_scan.finding_count}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-semibold mb-4">Analysis</h3>
                <SafeHtml value={docResult.analysis} className="prose prose-sm max-w-none whitespace-pre-wrap" />
              </div>

              {docResult.recommendations.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h3 className="text-lg font-semibold mb-4">Recommendations</h3>
                  {docResult.recommendations.map((r, i) => (
                    <div key={i} className={`p-3 rounded mb-2 ${severityColor(r.priority)}`}>
                      <SafeHtml value={r.action} className="font-medium" />
                      <SafeHtml value={r.description} className="text-sm" />
                    </div>
                  ))}
                </div>
              )}

              {docResult.appeal_strategy && (
                <div className="bg-green-50 p-6 rounded-lg border border-green-200">
                  <h3 className="text-lg font-semibold mb-2 text-green-800">Appeal Strategy</h3>
                  <SafeHtml value={docResult.appeal_strategy} className="text-green-700" />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'claim' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Predict Denial Risk</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Patient ID</label>
                <input type="number" value={formData.patient_id} onChange={e => setFormData({...formData, patient_id: Number(e.target.value)})} 
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Provider ID</label>
                <input type="number" value={formData.provider_id} onChange={e => setFormData({...formData, provider_id: Number(e.target.value)})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Diagnosis Codes (comma-separated)</label>
                <input type="text" onChange={e => setFormData({...formData, diagnosis_codes: e.target.value.split(',').map(s => s.trim()).filter(Boolean)})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Procedure Codes (comma-separated)</label>
                <input type="text" 
                  onChange={e => setFormData({...formData, procedure_codes: e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean)})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Claim Amount</label>
                <input type="number" 
                  onChange={e => setFormData({...formData, claim_data: {...formData.claim_data, amount: Number(e.target.value)}})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" />
              </div>
              <button type="submit" disabled={loading}
                className="w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 disabled:opacity-50">
                {loading ? 'Analyzing...' : 'Predict Denial Risk'}
              </button>
            </form>
          </div>

          {result && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-semibold mb-4">Prediction Results</h3>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-gray-600">Denial Risk:</span>
                  <span className={`text-2xl font-bold ${result.denial_prediction > 0.5 ? 'text-red-600' : result.denial_prediction > 0.3 ? 'text-yellow-600' : 'text-green-600'}`}>
                    {(result.denial_prediction * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div className={`h-4 rounded-full ${result.denial_prediction > 0.5 ? 'bg-red-600' : result.denial_prediction > 0.3 ? 'bg-yellow-500' : 'bg-green-500'}`}
                    style={{ width: `${result.denial_prediction * 100}%` }} />
                </div>
                <p className="mt-2 text-sm text-gray-500">Confidence: {(result.denial_confidence * 100).toFixed(1)}%</p>
                {result.human_review_required && (
                  <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                    <div className="font-semibold">Human review required</div>
                    <div className="mt-1">
                      Route this claim to billing review before the next payer action.
                    </div>
                    {result.human_review_reasons.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {result.human_review_reasons.map((reason) => (
                          <span key={reason} className="rounded bg-white px-2 py-1 text-xs font-medium text-red-700">
                            {reviewReasonLabel(reason)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-semibold mb-4">Denial Reasons</h3>
                {result.denial_reasons.map((r: DenialReason, i: number) => (
                  <div key={i} className={`p-3 rounded mb-2 ${severityColor(r.severity)}`}>
                    <SafeHtml value={r.reason} className="font-medium" />
                    {r.code && <div className="text-sm">Code: <SafeHtml value={r.code} inline /></div>}
                  </div>
                ))}
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-semibold mb-4">Recommendations</h3>
                {result.recommendations.map((r: Recommendation, i: number) => (
                  <div key={i} className="border-l-4 border-primary-500 pl-4 mb-3">
                    <SafeHtml value={r.action} className="font-medium" />
                    <SafeHtml value={r.description} className="text-sm text-gray-600" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
