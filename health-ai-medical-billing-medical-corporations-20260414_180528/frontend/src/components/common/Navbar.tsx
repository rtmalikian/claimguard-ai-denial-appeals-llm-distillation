import { Link } from 'react-router-dom';
import type { AuthUser } from '../../api/client';

interface NavbarProps {
  user: AuthUser;
  onLogout: () => void;
}

export default function Navbar({ user, onLogout }: NavbarProps) {
  const canGenerateAppeals = user.role === 'admin' || user.role === 'billing_staff';
  const canRunDenialWorkflow = user.role === 'admin' || user.role === 'billing_staff';

  return (
    <nav className="bg-primary-600 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="text-xl font-bold">ClaimGuard AI</Link>
            <div className="ml-10 flex space-x-4">
              <Link to="/dashboard" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Dashboard</Link>
              <Link to="/claims" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Claims</Link>
              <Link to="/patients" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Patients</Link>
              {canGenerateAppeals && (
                <Link to="/appeals" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Appeals</Link>
              )}
              {canRunDenialWorkflow && (
                <Link to="/denial-workflow" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Workflow</Link>
              )}
              <Link to="/analytics" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Analytics</Link>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm font-medium">{user.full_name || user.email}</div>
              <div className="text-xs uppercase tracking-wide text-primary-100">{user.role.replace('_', ' ')}</div>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="rounded-md bg-primary-700 px-3 py-2 text-sm font-medium hover:bg-primary-800"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
