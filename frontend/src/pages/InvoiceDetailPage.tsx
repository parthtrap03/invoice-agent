import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Play } from 'lucide-react';
import { api } from '../services/api';
import type { InvoiceDetail } from '../types';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

const statusColor: Record<string, string> = {
  APPROVED: 'bg-green-100 text-green-800',
  COMPLETED: 'bg-green-100 text-green-800',
  REVIEW_REQUIRED: 'bg-yellow-100 text-yellow-800',
  UPLOADED: 'bg-blue-100 text-blue-800',
  REJECTED: 'bg-red-100 text-red-800',
  AUTO_APPROVE: 'bg-green-100 text-green-800',
};

const riskBarColor: Record<string, string> = {
  LOW: 'bg-green-500',
  MEDIUM: 'bg-yellow-500',
  HIGH: 'bg-red-500',
};

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [inv, setInv] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    api.getInvoice(id).then(setInv).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  const runProcessing = async () => {
    if (!id) return;
    setProcessing(true);
    setError('');
    try {
      await api.processInvoice(id);
      const fresh = await api.getInvoice(id);
      setInv(fresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Processing failed');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) return <div className="p-8 text-gray-500">Loading invoice...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!inv) return null;

  const d = inv.decision_result;
  const po = inv.po_match_result;
  const dup = inv.duplicate_result;
  const vr = inv.vendor_risk_result;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/invoices')} className="p-1.5 rounded hover:bg-gray-100">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h2 className="text-2xl font-bold">{inv.invoice_number}</h2>
          <p className="text-sm text-gray-500">{inv.vendor_name || 'Unknown vendor'}</p>
        </div>
        <span className={`ml-auto px-3 py-1 rounded text-sm font-medium ${statusColor[inv.status] || 'bg-gray-100'}`}>
          {inv.status.replace(/_/g, ' ')}
        </span>
        {['UPLOADED', 'EXTRACTED', 'EXTRACTION_FAILED'].includes(inv.status) && (
          <button
            onClick={runProcessing}
            disabled={processing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Play size={16} />
            {processing ? 'Processing...' : 'Process Invoice'}
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>
      )}

      {/* Invoice Info */}
      <section className="bg-white rounded-lg shadow-sm border p-5">
        <h3 className="font-semibold mb-3">Invoice Information</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><span className="text-gray-500 block">Subtotal</span><span className="font-medium">{fmt(inv.subtotal)}</span></div>
          <div><span className="text-gray-500 block">Tax</span><span className="font-medium">{fmt(inv.tax_amount)}</span></div>
          <div><span className="text-gray-500 block">Total</span><span className="font-bold text-lg">{fmt(inv.total_amount)}</span></div>
          <div><span className="text-gray-500 block">Currency</span><span className="font-medium">{inv.currency}</span></div>
          <div><span className="text-gray-500 block">Invoice Date</span><span className="font-medium">{inv.invoice_date || '—'}</span></div>
          <div><span className="text-gray-500 block">Due Date</span><span className="font-medium">{inv.due_date || '—'}</span></div>
          <div><span className="text-gray-500 block">Payment Terms</span><span className="font-medium">{inv.payment_terms}</span></div>
          <div><span className="text-gray-500 block">PO Number</span><span className="font-medium">{inv.po_number || '—'}</span></div>
        </div>
      </section>

      {/* Line Items */}
      {inv.items.length > 0 && (
        <section className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-3">Line Items</h3>
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr>
                <th className="text-left py-2 font-medium text-gray-600">Description</th>
                <th className="text-right py-2 font-medium text-gray-600">Qty</th>
                <th className="text-right py-2 font-medium text-gray-600">Unit Price</th>
                <th className="text-right py-2 font-medium text-gray-600">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {inv.items.map(item => (
                <tr key={item.id}>
                  <td className="py-2">{item.description}</td>
                  <td className="py-2 text-right">{item.quantity}</td>
                  <td className="py-2 text-right font-mono">{fmt(item.unit_price)}</td>
                  <td className="py-2 text-right font-mono font-medium">{fmt(item.total_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* AI Decision */}
      {d && (
        <section className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-3">AI Decision</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <span className="text-gray-500 text-sm block mb-1">Decision</span>
              <span className={`inline-block px-3 py-1 rounded text-sm font-bold ${statusColor[d.decision] || 'bg-gray-100'}`}>
                {d.decision.replace(/_/g, ' ')}
              </span>
            </div>
            <div>
              <span className="text-gray-500 text-sm block mb-1">Risk Score</span>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold">{d.risk_score}</span>
                <span className="text-gray-400">/100</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div
                  className={`h-2 rounded-full ${riskBarColor[d.risk_level] || 'bg-gray-400'}`}
                  style={{ width: `${d.risk_score}%` }}
                />
              </div>
            </div>
            <div>
              <span className="text-gray-500 text-sm block mb-1">Risk Level</span>
              <span className={`inline-block px-3 py-1 rounded text-sm font-bold ${
                d.risk_level === 'LOW' ? 'bg-green-100 text-green-800' : d.risk_level === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
              }`}>{d.risk_level}</span>
            </div>
          </div>
          <div>
            <span className="text-gray-500 text-sm block mb-2">Reasons</span>
            <ul className="space-y-1">
              {d.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-yellow-500 mt-0.5">⚠</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {/* PO Match */}
      {po && (
        <section className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-3">PO Match</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><span className="text-gray-500 block">PO Number</span><span className="font-medium">{po.po_number}</span></div>
            <div><span className="text-gray-500 block">PO Amount</span><span className="font-medium">{fmt(po.po_amount)}</span></div>
            <div><span className="text-gray-500 block">Invoice Amount</span><span className="font-medium">{fmt(po.invoice_amount)}</span></div>
            <div>
              <span className="text-gray-500 block">Variance</span>
              <span className={`font-bold ${po.variance_acceptable ? 'text-green-600' : 'text-red-600'}`}>
                {po.variance_pct}%
              </span>
              <span className="text-xs text-gray-400 ml-1">(threshold: {po.threshold}%)</span>
            </div>
          </div>
        </section>
      )}

      {/* Duplicate Check */}
      {dup && (
        <section className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-3">Duplicate Check</h3>
          <div className="text-sm">
            {dup.duplicate ? (
              <div className="text-red-600 font-medium">
                ⚠ Potential duplicate found: {dup.matched_invoice} (confidence: {(dup.confidence * 100).toFixed(0)}%)
              </div>
            ) : (
              <div className="text-green-600 font-medium">
                ✓ No duplicate found (confidence: {(dup.confidence * 100).toFixed(0)}%)
              </div>
            )}
          </div>
        </section>
      )}

      {/* Vendor Risk */}
      {vr && (
        <section className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-3">Vendor Risk</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><span className="text-gray-500 block">Vendor</span><span className="font-medium">{vr.vendor}</span></div>
            <div><span className="text-gray-500 block">Status</span><span className="font-medium">{vr.status}</span></div>
            <div>
              <span className="text-gray-500 block">Risk Level</span>
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                vr.risk_level === 'LOW' ? 'bg-green-100 text-green-800' : vr.risk_level === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
              }`}>{vr.risk_level}</span>
            </div>
            <div><span className="text-gray-500 block">Risk Score</span><span className="font-medium">{vr.risk_score}</span></div>
          </div>
        </section>
      )}
    </div>
  );
}
