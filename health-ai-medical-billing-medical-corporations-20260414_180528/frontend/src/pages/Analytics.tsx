import { useEffect, useState } from 'react';
import { analyticsApi } from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

interface Trend {
  period: string;
  total_claims: number;
  predicted_denials: number;
  denial_rate: number;
  top_reasons: { reason: string; count: number }[];
}

export default function Analytics() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    analyticsApi.getDenialTrends(30)
      .then(res => setTrends(res.data.trends))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Denial Analytics</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Claim Volume Trends</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="total_claims" stroke="#3b82f6" name="Total Claims" />
              <Line type="monotone" dataKey="predicted_denials" stroke="#ef4444" name="Predicted Denials" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Denial Rate by Period</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="denial_rate" fill="#ef4444" name="Denial Rate" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Top Denial Reasons by Period</h2>
        {trends.map((t, i) => (
          <div key={i} className="mb-6">
            <h3 className="font-medium text-gray-700 mb-2">{t.period}</h3>
            {t.top_reasons.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {t.top_reasons.map((r, j) => (
                  <span key={j} className="px-3 py-1 bg-red-50 text-red-700 rounded-full text-sm">
                    {r.reason} ({r.count})
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">No denial reasons recorded</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}