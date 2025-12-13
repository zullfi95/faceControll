import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Skeleton from './components/ui/Skeleton';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import SkipLink from './components/accessibility/SkipLink';
import LiveRegion from './components/accessibility/LiveRegion';
import { useKeyboardNavigation } from './hooks/useKeyboardNavigation';
// Lazy load pages for better performance
const UsersPage = lazy(() => import('./pages/UsersPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const DeviceSettingsPage = lazy(() => import('./pages/DeviceSettingsPage'));
const EventsPage = lazy(() => import('./pages/EventsPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const UsersManagementPage = lazy(() => import('./pages/UsersManagementPage'));
const WorkShiftsPage = lazy(() => import('./pages/WorkShiftsPage'));
import { useAuth } from './contexts/AuthContext';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Загрузка...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function AppContent() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [liveMessage, setLiveMessage] = React.useState('');

  // Глобальные горячие клавиши
  useKeyboardNavigation({
    'ctrl+k': (e) => {
      e.preventDefault();
      // Можно добавить поиск или другие действия
    },
    '1': (e) => {
      if (e.ctrlKey && user) {
        e.preventDefault();
        navigate('/users');
        setLiveMessage('Переход на страницу Сотрудники');
      }
    },
    '2': (e) => {
      if (e.ctrlKey && user) {
        e.preventDefault();
        navigate('/events');
        setLiveMessage('Переход на страницу События');
      }
    },
    '3': (e) => {
      if (e.ctrlKey && user) {
        e.preventDefault();
        navigate('/reports');
        setLiveMessage('Переход на страницу Отчеты');
      }
    },
    '4': (e) => {
      if (e.ctrlKey && user) {
        e.preventDefault();
        navigate('/settings');
        setLiveMessage('Переход на страницу Настройки');
      }
    },
  });

  return (
    <div className="min-h-screen bg-gray-100">
      <SkipLink />
      <LiveRegion message={liveMessage} priority="polite" />
      {user ? (
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar for desktop */}
          <Sidebar />

            {/* Main content area */}
            <div className="flex flex-col flex-1 overflow-hidden">
              {/* Header */}
              <Header />

              {/* Main content */}
              <main id="main-content" className="flex-1 overflow-y-auto bg-gray-100" tabIndex={-1}>
                <div className="py-6 px-4 sm:px-6 lg:px-8">
                  <Suspense fallback={
                    <div className="space-y-4">
                      <Skeleton className="h-8 w-64" />
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Skeleton className="h-32" />
                        <Skeleton className="h-32" />
                        <Skeleton className="h-32" />
                      </div>
                      <Skeleton className="h-96" />
                    </div>
                  }>
                    <Routes>
                      <Route path="/" element={<Navigate to="/users" replace />} />
                      <Route
                        path="/users"
                        element={
                          <PrivateRoute>
                            <UsersPage />
                          </PrivateRoute>
                        }
                      />
                      <Route
                        path="/events"
                        element={
                          <PrivateRoute>
                            <EventsPage />
                          </PrivateRoute>
                        }
                      />
                      <Route
                        path="/reports"
                        element={
                          <PrivateRoute>
                            <ReportsPage />
                          </PrivateRoute>
                        }
                      />
                      <Route
                        path="/settings"
                        element={
                          <PrivateRoute>
                            <DeviceSettingsPage />
                          </PrivateRoute>
                        }
                      />
                      <Route
                        path="/users-management"
                        element={
                          <PrivateRoute>
                            <UsersManagementPage />
                          </PrivateRoute>
                        }
                      />
                      <Route
                        path="/work-shifts"
                        element={
                          <PrivateRoute>
                            <WorkShiftsPage />
                          </PrivateRoute>
                        }
                      />
                      <Route path="*" element={<Navigate to="/users" replace />} />
                    </Routes>
                  </Suspense>
                </div>
              </main>
            </div>
          </div>
        ) : (
          <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center">
              <Skeleton className="h-96 w-96" />
            </div>
          }>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </Suspense>
        )}
      </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;

