// ---- Pagination ----
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ---- Vendor ----
export interface Vendor {
  id: string;
  vendor_code: string;
  name: string;
  category: string;
  status: string;
  contact_email: string;
  tax_id: string;
  risk_score: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ---- Purchase Order ----
export interface POItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  vendor_id: string;
  total_amount: number;
  currency: string;
  status: string;
  issue_date: string;
  expiry_date: string | null;
  department: string;
  created_at: string;
  items: POItem[];
  vendor_name: string | null;
}

// ---- Invoice ----
export interface InvoiceItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface InvoiceListItem {
  id: string;
  invoice_number: string;
  vendor_name: string | null;
  total_amount: number;
  currency: string;
  status: string;
  risk_level: string | null;
  risk_score: number | null;
  ai_decision: string | null;
  invoice_date: string | null;
  created_at: string;
}

export interface InvoiceDetail {
  id: string;
  invoice_number: string;
  vendor_id: string | null;
  po_id: string | null;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  currency: string;
  invoice_date: string | null;
  due_date: string | null;
  payment_terms: string;
  status: string;
  risk_level: string | null;
  risk_score: number | null;
  ai_decision: string | null;
  ai_confidence: number | null;
  extracted_data: Record<string, unknown> | null;
  validation_result: Record<string, unknown> | null;
  po_match_result: {
    po_number: string;
    po_amount: number;
    invoice_amount: number;
    variance_pct: number;
    variance_acceptable: boolean;
    threshold: number;
  } | null;
  duplicate_result: {
    duplicate: boolean;
    confidence: number;
    matched_invoice: string | null;
  } | null;
  policy_result: Record<string, unknown> | null;
  vendor_risk_result: {
    vendor: string;
    status: string;
    risk_level: string;
    risk_score: number;
    contract_valid?: boolean;
  } | null;
  decision_result: {
    decision: string;
    risk_score: number;
    confidence: number;
    risk_level: string;
    reasons: string[];
  } | null;
  source_file_key: string | null;
  created_at: string;
  updated_at: string;
  items: InvoiceItem[];
  vendor_name: string | null;
  po_number: string | null;
}

// ---- Approval ----
export interface Approval {
  id: string;
  invoice_id: string;
  requested_by: string;
  approved_by: string | null;
  status: string;
  risk_level: string;
  reasons: string | null;
  evidence: string | null;
  comments: string | null;
  requested_at: string;
  decided_at: string | null;
  invoice_number: string | null;
  vendor_name: string | null;
  total_amount: number | null;
}

// ---- Metrics ----
export interface DashboardMetrics {
  total_invoices: number;
  by_status: Record<string, number>;
  total_amount: number;
  avg_risk_score: number | null;
  high_risk_count: number;
  pending_approvals: number;
  automation_rate: number;
}

// ---- Finance ----
export interface FinanceQueryResponse {
  answer: string;
  sql_query: string | null;
  data: Record<string, unknown>[] | null;
  tools_used: string[];
  sources: string[];
  trace_id: string | null;
}
