import type {
  PaginatedResponse,
  InvoiceListItem,
  InvoiceDetail,
  Vendor,
  PurchaseOrder,
  Approval,
  DashboardMetrics,
} from '../types';

const BASE = '/api';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => request<{ status: string; version: string; environment: string }>('/health'),

  // Invoices
  listInvoices: (page = 1, pageSize = 20, status?: string) => {
    const p = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) p.set('status', status);
    return request<PaginatedResponse<InvoiceListItem>>(`/invoices?${p}`);
  },
  getInvoice: (id: string) => request<InvoiceDetail>(`/invoices/${id}`),
  uploadInvoice: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${BASE}/invoices/upload`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error('Upload failed');
    return res.json();
  },
  processInvoice: (id: string) =>
    request<{ message: string }>(`/invoices/${id}/process`, { method: 'POST' }),

  // Vendors
  listVendors: (page = 1, pageSize = 20) =>
    request<PaginatedResponse<Vendor>>(`/vendors?page=${page}&page_size=${pageSize}`),

  // Purchase Orders
  listPurchaseOrders: (page = 1, pageSize = 20) =>
    request<PaginatedResponse<PurchaseOrder>>(`/purchase-orders?page=${page}&page_size=${pageSize}`),

  // Approvals
  listApprovals: () => request<PaginatedResponse<Approval>>('/approvals'),
  approveInvoice: (id: string, comments?: string) =>
    request<Approval>(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ comments }),
    }),
  rejectInvoice: (id: string, comments?: string) =>
    request<Approval>(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ comments }),
    }),

  // Metrics
  getMetrics: () => request<DashboardMetrics>('/metrics'),
};
