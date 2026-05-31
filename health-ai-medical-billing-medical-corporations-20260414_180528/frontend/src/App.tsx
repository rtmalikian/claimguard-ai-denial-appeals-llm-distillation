import { type ReactNode, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Claims from './pages/Claims';
import Analytics from './pages/Analytics';
import Login from './pages/Login';
import Patients from './pages/Patients';
import Appeals from './pages/Appeals';
import DenialWorkflow from './pages/DenialWorkflow';
import Navbar from './components/common/Navbar';
import {
  AuthUser,
  SESSION_TIMEOUT_CHECK_INTERVAL_MS,
  authApi,
  clearAuthSession,
  enforceAuthSessionTimeout,
  getStoredUser,
  markAuthActivity,
} from './api/client';

interface ProtectedRouteProps {
  user: AuthUser | null;
  children: ReactNode;
}

function ProtectedRoute({ user, children }: ProtectedRouteProps) {
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());

  useEffect(() => {
    if (!user) return undefined;

    const handleTimeoutCheck = () => {
      if (!enforceAuthSessionTimeout()) return false;
      setUser(null);
      return true;
    };

    if (handleTimeoutCheck()) return undefined;

    const handleActivity = () => {
      if (handleTimeoutCheck()) return;
      markAuthActivity();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') handleActivity();
    };
    const activityEvents = ['click', 'keydown', 'mousedown', 'mousemove', 'scroll', 'touchstart'];
    const activityOptions: AddEventListenerOptions = { passive: true };

    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, activityOptions);
    });
    document.addEventListener('visibilitychange', handleVisibilityChange);
    const timeoutInterval = window.setInterval(handleTimeoutCheck, SESSION_TIMEOUT_CHECK_INTERVAL_MS);

    return () => {
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity, activityOptions);
      });
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.clearInterval(timeoutInterval);
    };
  }, [user]);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.error(err);
    } finally {
      clearAuthSession();
      setUser(null);
    }
  };

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="min-h-screen bg-gray-50">
        {user && <Navbar user={user} onLogout={handleLogout} />}
        <Routes>
          <Route path="/" element={<Navigate to={user ? '/dashboard' : '/login'} replace />} />
          <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login onLogin={setUser} />} />
          <Route path="/dashboard" element={<ProtectedRoute user={user}><Dashboard /></ProtectedRoute>} />
          <Route path="/claims" element={<ProtectedRoute user={user}><Claims /></ProtectedRoute>} />
          <Route path="/patients" element={<ProtectedRoute user={user}><Patients currentUser={user} /></ProtectedRoute>} />
          <Route path="/appeals" element={<ProtectedRoute user={user}><Appeals currentUser={user} /></ProtectedRoute>} />
          <Route path="/denial-workflow" element={<ProtectedRoute user={user}><DenialWorkflow currentUser={user} /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute user={user}><Analytics /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
