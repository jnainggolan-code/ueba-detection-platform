import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import RiskDashboard from './pages/RiskDashboard';
import LogViewer from './pages/LogViewer';
import UserDetection from './pages/UserDetection';
import Alerts from './pages/Alerts';
import SettingsPage from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<RiskDashboard />} />
        <Route path="/events" element={<LogViewer />} />
        <Route path="/detections" element={<UserDetection />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
