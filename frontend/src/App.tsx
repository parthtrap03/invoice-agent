import { Routes, Route, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Upload,
  CheckCircle,
  MessageSquare,
  Building2,
  ShoppingCart,
} from 'lucide-react';
import DashboardPage from './pages/DashboardPage';
import InvoiceListPage from './pages/InvoiceListPage';
import InvoiceDetailPage from './pages/InvoiceDetailPage';
import UploadPage from './pages/UploadPage';
import ApprovalCenterPage from './pages/ApprovalCenterPage';
import FinanceAnalystPage from './pages/FinanceAnalystPage';
import VendorsPage from './pages/VendorsPage';
import PurchaseOrdersPage from './pages/PurchaseOrdersPage';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/invoices', icon: FileText, label: 'Invoices' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/approvals', icon: CheckCircle, label: 'Approvals' },
  { to: '/analyst', icon: MessageSquare, label: 'Analyst' },
  { to: '/vendors', icon: Building2, label: 'Vendors' },
  { to: '/purchase-orders', icon: ShoppingCart, label: 'POs' },
];

export default function App() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-slate-800 text-white flex flex-col shrink-0">
        <div className="px-4 py-5 border-b border-slate-700">
          <h1 className="text-lg font-bold tracking-tight">Finance Agent</h1>
          <p className="text-xs text-slate-400 mt-0.5">AI-Powered AP System</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-slate-700 text-white font-medium'
                    : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-slate-700 text-xs text-slate-500">
          v0.1.0 · Demo Mode
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/invoices" element={<InvoiceListPage />} />
          <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/approvals" element={<ApprovalCenterPage />} />
          <Route path="/analyst" element={<FinanceAnalystPage />} />
          <Route path="/vendors" element={<VendorsPage />} />
          <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
        </Routes>
      </main>
    </div>
  );
}
