import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Approval, PaginatedResponse } from '../types';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

export default function ApprovalCenterPage() {
  const [data, setData] = useState<PaginatedResponse<Approval> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api.listApprovals().then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    setActionLoading(id);
    try {
      if (action === 'approve') await api.approveInvoice(id);
      else await api.rejectInvoice(id, 'Rejected by reviewer');
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <div className="p-8 text-gray-500">Loading approvals...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const items = data?.items || [];

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-2xl font-bold">Approval Center</h2>

      {items.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center text-gray-500">
          No pending approvals
        </div>
      ) : (
        <div className="space-y-4">
          {items.map(a => (
            <div key={a.id} className="bg-white rounded-lg shadow-sm border p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-semibold text-lg">{a.invoice_number || 'Unknown'}</div>
                  <div className="text-sm text-gray-500">{a.vendor_name || 'Unknown vendor'}</div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-lg">{a.total_amount ? fmt(a.total_amount) : '—'}</div>
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    a.risk_level === 'HIGH' ? 'bg-red-100 text-red-800'
                    : a.risk_level === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-green-100 text-green-800'
                  }`}>{a.risk_level} risk</span>
                </div>
              </div>

              {a.reasons && (
                <div className="mb-3 text-sm text-gray-600 bg-gray-50 rounded p-3">
                  <span className="font-medium block mb-1">Reasons:</span>
                  {a.reasons}
                </div>
              )}

              {a.evidence && (
                <div className="mb-3 text-sm text-gray-500 bg-gray-50 rounded p-3">
                  <span className="font-medium block mb-1">Evidence:</span>
                  {a.evidence}
                </div>
              )}

              <div className="flex gap-3 justify-end">
                <button
                  disabled={actionLoading === a.id}
                  onClick={() => handleAction(a.id, 'reject')}
                  className="px-4 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50 text-sm font-medium disabled:opacity-50"
                >
                  Reject
                </button>
                <button
                  disabled={actionLoading === a.id}
                  onClick={() => handleAction(a.id, 'approve')}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium disabled:opacity-50"
                >
                  Approve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
