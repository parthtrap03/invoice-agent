import { useEffect, useState } from 'react';
import { FileText, AlertTriangle, Clock, Zap, TrendingUp } from 'lucide-react';
import { api } from '../services/api';
import type { DashboardMetrics } from '../types';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getMetrics().then(setMetrics).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-gray-500">Loading dashboard...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!metrics) return null;

  const cards = [
    { label: 'Total Invoices', value: metrics.total_invoices, icon: FileText, color: 'bg-blue-50 text-blue-700' },
    { label: 'Total Amount', value: fmt(metrics.total_amount), icon: TrendingUp, color: 'bg-green-50 text-green-700' },
    { label: 'Pending Approvals', value: metrics.pending_approvals, icon: Clock, color: 'bg-yellow-50 text-yellow-700' },
    { label: 'High Risk', value: metrics.high_risk_count, icon: AlertTriangle, color: 'bg-red-50 text-red-700' },
    { label: 'Automation Rate', value: `${(metrics.automation_rate * 100).toFixed(1)}%`, icon: Zap, color: 'bg-purple-50 text-purple-700' },
  ];

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">Finance Dashboard</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {cards.map(c => (
          <div key={c.label} className="bg-white rounded-lg shadow-sm border p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{c.label}</span>
              <span className={`p-1.5 rounded-md ${c.color}`}><c.icon size={16} /></span>
            </div>
            <div className="text-2xl font-bold">{c.value}</div>
          </div>
        ))}
      </div>

      {/* Status breakdown */}
      <div className="bg-white rounded-lg shadow-sm border p-5">
        <h3 className="font-semibold mb-3">Invoices by Status</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {Object.entries(metrics.by_status).map(([status, count]) => (
            <div key={status} className="text-center p-3 bg-gray-50 rounded-md">
              <div className="text-lg font-bold">{count}</div>
              <div className="text-xs text-gray-500 mt-0.5">{status.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      </div>

      {metrics.avg_risk_score !== null && (
        <div className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-1">Average Risk Score</h3>
          <div className="text-3xl font-bold">{metrics.avg_risk_score.toFixed(1)}<span className="text-sm font-normal text-gray-500"> / 100</span></div>
        </div>
      )}
    </div>
  );
}
