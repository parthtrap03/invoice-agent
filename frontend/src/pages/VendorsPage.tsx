import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Vendor } from '../types';

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listVendors(1, 100)
      .then(r => setVendors(r.items))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-gray-500">Loading vendors...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Vendors</h2>
        <p className="text-sm text-gray-500 mt-1">
          Master data the rules engine validates every invoice against — inactive or
          high-risk vendors cause automatic rejection or review.
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Vendor</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Code</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Tax ID</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Risk Score</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {vendors.map(v => (
              <tr key={v.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium">{v.name}</div>
                  <div className="text-xs text-gray-400">{v.contact_email}</div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{v.vendor_code}</td>
                <td className="px-4 py-3 font-mono text-xs">{v.tax_id}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    v.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {v.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-20 bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          v.risk_score > 70 ? 'bg-red-500' : v.risk_score > 40 ? 'bg-yellow-500' : 'bg-green-500'
                        }`}
                        style={{ width: `${Math.min(v.risk_score, 100)}%` }}
                      />
                    </div>
                    <span className="font-medium">{v.risk_score}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {vendors.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">No vendors yet — run setup_demo.py</div>
        )}
      </div>
    </div>
  );
}
