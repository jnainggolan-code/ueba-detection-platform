import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

const pageTitles: Record<string, string> = {
  '/': 'Risk Dashboard',
  '/events': 'Log Viewer',
  '/detections': 'User Detection',
  '/alerts': 'Alerts',
  '/settings': 'Settings',
};

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const title = pageTitles[location.pathname] ?? 'UEBA Detection Platform';

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title={title} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
