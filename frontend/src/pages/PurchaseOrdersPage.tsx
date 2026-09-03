import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { PurchaseOrder } from '../types';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

export default function PurchaseOrdersPage() {
  const [pos, setPos] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listPurchaseOrders(1, 100)
      .then(r => setPos(r.items))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-gray-500">Loading purchase orders...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Purchase Orders</h2>
        <p className="text-sm text-gray-500 mt-1">
          Invoices are 2-way matched against these — amounts more than 2% over the PO
          are flagged for review.
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">PO Number</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Vendor</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Items</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Amount</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Issue Date</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {pos.map(po => (
              <tr key={po.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono font-medium">{po.po_number}</td>
                <td className="px-4 py-3">{po.vendor_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600">
                  {po.items?.map(i => `${i.description} × ${i.quantity}`).join(', ') || '—'}
                </td>
                <td className="px-4 py-3 text-right font-mono font-medium">{fmt(po.total_amount)}</td>
                <td className="px-4 py-3 text-gray-600">{po.issue_date}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    po.status === 'ACTIVE' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {po.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {pos.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">No purchase orders yet — run setup_demo.py</div>
        )}
      </div>
    </div>
  );
}
