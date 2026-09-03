import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { InvoiceListItem, PaginatedResponse } from '../types';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

const statusColor: Record<string, string> = {
  APPROVED: 'bg-green-100 text-green-800',
  COMPLETED: 'bg-green-100 text-green-800',
  AUTO_APPROVE: 'bg-green-100 text-green-800',
  REVIEW_REQUIRED: 'bg-yellow-100 text-yellow-800',
  UPLOADED: 'bg-blue-100 text-blue-800',
  REJECTED: 'bg-red-100 text-red-800',
  REJECT: 'bg-red-100 text-red-800',
};

const riskColor: Record<string, string> = {
  LOW: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-red-100 text-red-800',
};

export default function InvoiceListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<InvoiceListItem> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    api.listInvoices(page).then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [page]);

  if (loading) return <div className="p-8 text-gray-500">Loading invoices...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!data) return null;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Invoices</h2>
        <span className="text-sm text-gray-500">{data.total} total</span>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Invoice #</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Vendor</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Amount</th>
              <th className="text-center px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-center px-4 py-3 font-medium text-gray-600">Risk</th>
              <th className="text-center px-4 py-3 font-medium text-gray-600">AI Decision</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.items.map(inv => (
              <tr
                key={inv.id}
                onClick={() => navigate(`/invoices/${inv.id}`)}
                className="hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                <td className="px-4 py-3 text-gray-600">{inv.vendor_name || '—'}</td>
                <td className="px-4 py-3 text-right font-mono">{fmt(inv.total_amount)}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusColor[inv.status] || 'bg-gray-100 text-gray-700'}`}>
                    {inv.status.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {inv.risk_level && (
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${riskColor[inv.risk_level] || 'bg-gray-100'}`}>
                      {inv.risk_level}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  {inv.ai_decision && (
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusColor[inv.ai_decision] || 'bg-gray-100'}`}>
                      {inv.ai_decision.replace(/_/g, ' ')}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500">{inv.invoice_date || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">Page {data.page} of {data.total_pages}</span>
        <div className="space-x-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 border rounded-md disabled:opacity-40 hover:bg-gray-50"
          >
            Previous
          </button>
          <button
            disabled={page >= data.total_pages}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 border rounded-md disabled:opacity-40 hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
