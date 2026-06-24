import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { PageLoading } from '@/components/shared/LoadingSpinner';
import {
  Activity,
  Database,
  Clock,
  Webhook,
  Shield,
  CheckCircle,
  XCircle,
  RefreshCw,
  Settings as SettingsIcon,
} from 'lucide-react';
import api from '@/lib/api';

interface HealthResponse {
  status: string;
  module: string;
  version: string;
  db_connected: boolean;
}

interface WebhookStatus {
  last_event: string | null;
  total_events: number;
  active: boolean;
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [webhook, setWebhook] = useState<WebhookStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, eventsRes] = await Promise.all([
        api.get<HealthResponse>('/v1/health'),
        api.get('/v1/events', { params: { limit: 1 } }).catch(() => ({ data: { data: [], total: 0 } })),
      ]);

      setHealth(healthRes.data);

      const totalEvents = eventsRes.data?.total ?? 0;
      const lastEvent = eventsRes.data?.data?.[0]?.timestamp ?? null;
      setWebhook({
        last_event: lastEvent,
        total_events: totalEvents,
        active: totalEvents > 0,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <PageLoading />;

  const lastSync = webhook?.last_event
    ? new Date(webhook.last_event).toLocaleString('en-US', {
        dateStyle: 'medium',
        timeStyle: 'medium',
      })
    : 'No events yet';

  const apiOk = health?.status === 'ok';

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SettingsIcon className="w-6 h-6 text-ueba-accent-blue" />
          <h1 className="text-lg font-bold text-ueba-text-primary">Settings</h1>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-xs text-ueba-accent-blue hover:underline"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <Card>
          <CardContent className="py-3">
            <p className="text-xs text-ueba-accent-red">Error loading settings: {error}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Activity className="w-4 h-4 text-ueba-accent-blue" />
            Connection Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center justify-between p-3 rounded bg-ueba-bg-deep border border-ueba-border">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${apiOk ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
                  {apiOk
                    ? <CheckCircle className="w-4 h-4 text-emerald-400" />
                    : <XCircle className="w-4 h-4 text-ueba-accent-red" />
                  }
                </div>
                <div>
                  <p className="text-xs font-semibold text-ueba-text-primary">API Status</p>
                  <p className="text-[10px] text-ueba-text-muted">REST API endpoint</p>
                </div>
              </div>
              <Badge variant={apiOk ? 'success' : 'danger'}>
                {apiOk ? 'Connected' : 'Disconnected'}
              </Badge>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-ueba-bg-deep border border-ueba-border">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${health?.db_connected ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
                  {health?.db_connected
                    ? <Database className="w-4 h-4 text-emerald-400" />
                    : <XCircle className="w-4 h-4 text-ueba-accent-red" />
                  }
                </div>
                <div>
                  <p className="text-xs font-semibold text-ueba-text-primary">Database</p>
                  <p className="text-[10px] text-ueba-text-muted">PostgreSQL backend</p>
                </div>
              </div>
              <Badge variant={health?.db_connected ? 'success' : 'danger'}>
                {health?.db_connected ? 'Connected' : 'Disconnected'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Clock className="w-4 h-4 text-ueba-accent-yellow" />
              Last Sync
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold text-ueba-text-primary">{lastSync}</p>
            <p className="text-xs text-ueba-text-muted mt-1">
              {webhook?.total_events && webhook.total_events > 0
                ? webhook.total_events.toLocaleString() + ' total events processed'
                : 'Awaiting first event'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Shield className="w-4 h-4 text-ueba-accent-blue" />
              API Version
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge variant="info">v{health?.version ?? '-'}</Badge>
              <span className="text-xs text-ueba-text-muted">
                Module: {health?.module ?? '-'}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Webhook className="w-4 h-4 text-ueba-accent-green" />
            Webhook Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded bg-ueba-bg-deep border border-ueba-border">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center">
                  <Webhook className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ueba-text-primary">Wazuh Webhook</p>
                  <p className="text-[10px] text-ueba-text-muted">Endpoint: /api/v1/webhook/wazuh</p>
                </div>
              </div>
              <Badge variant={webhook?.active ? 'success' : 'warning'}>
                {webhook?.active ? 'Active' : 'Inactive'}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded bg-ueba-bg-deep border border-ueba-border">
                <p className="text-xs text-ueba-text-muted mb-1">Total Events Received</p>
                <p className="text-xl font-bold text-ueba-text-primary">
                  {(webhook?.total_events ?? 0).toLocaleString()}
                </p>
              </div>
              <div className="p-3 rounded bg-ueba-bg-deep border border-ueba-border">
                <p className="text-xs text-ueba-text-muted mb-1">Most Recent Event</p>
                <p className="text-sm font-medium text-ueba-text-primary truncate">
                  {webhook?.last_event
                    ? new Date(webhook.last_event).toLocaleString()
                    : 'N/A'}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
