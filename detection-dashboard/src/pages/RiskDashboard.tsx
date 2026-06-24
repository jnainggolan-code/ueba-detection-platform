import { useState, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  TrendingUp,
  Shield,
  Zap,
  Server,
  Users,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { MetricCard } from '@/components/shared/MetricCard';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { PageLoading } from '@/components/shared/LoadingSpinner';
import { useStats } from '@/hooks/useStats';

// Fallback mock for chart shapes when API data isn't available yet
const eventTrendData = [
  { hour: '00:00', events: 120, alerts: 3 },
  { hour: '01:00', events: 85, alerts: 1 },
  { hour: '02:00', events: 72, alerts: 0 },
  { hour: '03:00', events: 68, alerts: 2 },
  { hour: '04:00', events: 93, alerts: 1 },
  { hour: '05:00', events: 110, alerts: 4 },
  { hour: '06:00', events: 156, alerts: 3 },
  { hour: '07:00', events: 245, alerts: 7 },
  { hour: '08:00', events: 389, alerts: 12 },
  { hour: '09:00', events: 512, alerts: 15 },
  { hour: '10:00', events: 478, alerts: 11 },
  { hour: '11:00', events: 445, alerts: 9 },
  { hour: '12:00', events: 398, alerts: 8 },
  { hour: '13:00', events: 420, alerts: 10 },
  { hour: '14:00', events: 467, alerts: 13 },
  { hour: '15:00', events: 523, alerts: 14 },
  { hour: '16:00', events: 489, alerts: 11 },
  { hour: '17:00', events: 456, alerts: 9 },
  { hour: '18:00', events: 378, alerts: 6 },
  { hour: '19:00', events: 312, alerts: 5 },
  { hour: '20:00', events: 267, alerts: 4 },
  { hour: '21:00', events: 234, alerts: 3 },
  { hour: '22:00', events: 189, alerts: 2 },
  { hour: '23:00', events: 156, alerts: 1 },
];

const entityRiskData = [
  { name: 'svc-backup', score: 92, events: 3402 },
  { name: 'john.doe', score: 87, events: 1243 },
  { name: 'devops-bot', score: 81, events: 5621 },
  { name: 'api-gateway', score: 78, events: 8901 },
  { name: 'jane.smith', score: 65, events: 876 },
  { name: 'sarah.connor', score: 45, events: 678 },
  { name: 'mike.wilson', score: 34, events: 456 },
  { name: 'db-readonly', score: 22, events: 2341 },
];

const eventTypeData = [
  { name: 'Auth', value: 35 },
  { name: 'Network', value: 25 },
  { name: 'File', value: 18 },
  { name: 'Process', value: 12 },
  { name: 'Privilege', value: 7 },
  { name: 'Data', value: 3 },
];

const alertSeverityData = [
  { severity: 'Critical', count: 12, color: '#ef4444' },
  { severity: 'High', count: 18, color: '#f97316' },
  { severity: 'Medium', count: 27, color: '#eab308' },
  { severity: 'Low', count: 35, color: '#3b82f6' },
];

const timeRangeOptions = [
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
];

const chartColours = {
  green: '#10b981',
  red: '#ef4444',
  blue: '#3b82f6',
  yellow: '#eab308',
  purple: '#a855f7',
  slate: '#64748b',
};

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload) return null;
  return (
    <div className="bg-ueba-card border border-ueba-border rounded-lg p-3 shadow-xl">
      <p className="text-xs text-ueba-text-muted mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-xs font-mono" style={{ color: p.color }}>
          {p.name}: {p.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
}

function PieTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-ueba-card border border-ueba-border rounded-lg p-3 shadow-xl">
      <p className="text-xs font-medium text-ueba-text-primary">{d.name}</p>
      <p className="text-xs text-ueba-text-muted">{d.value}% of total</p>
    </div>
  );
}

export default function RiskDashboard() {
  const { stats, loading, error } = useStats();
  const [timeRange, setTimeRange] = useState('24h');

  const chartData = stats?.event_trend || eventTrendData;
  const totalAnomalies = useMemo(
    () => chartData.reduce((sum: number, h: { hour: string; events: number; alerts: number }) => sum + h.alerts, 0),
    [chartData]
  );

  if (loading) {
    return <PageLoading />;
  }

  return (
    <div className="space-y-6">
      {/* Time range selector */}
      <div className="flex justify-end">
        <Select
          options={timeRangeOptions}
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="w-44"
        />
      </div>

      {/* Metric cards row — data from API */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard
          title="Total Events"
          value={(stats?.total_events ?? 0).toLocaleString()}
          accent="blue"
          icon={<Activity />}
          subtitle="All time"
        />
        <MetricCard
          title="Active Alerts"
          value={stats?.active_alerts ?? 0}
          accent="red"
          icon={<AlertTriangle />}
          trend="up"
          trendValue="+12%"
        />
        <MetricCard
          title="Critical Alerts"
          value={stats?.critical_alerts ?? 0}
          accent="red"
          icon={<Zap />}
          subtitle="Requires immediate action"
        />
        <MetricCard
          title="Entities at Risk"
          value={stats?.entities_at_risk ?? 0}
          accent="yellow"
          icon={<Users />}
          trend="up"
          trendValue="+3"
        />
        <MetricCard
          title="Avg Risk Score"
          value={stats?.avg_risk_score ?? 0}
          accent="green"
          icon={<Shield />}
          trendValue="Moderate"
        />
        <MetricCard
          title="Events/hr"
          value={(stats?.events_last_hour ?? 0).toLocaleString()}
          accent="purple"
          icon={<TrendingUp />}
          subtitle="Last hour"
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Event & Alert Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-ueba-accent-blue" />
              Event & Alert Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="eventsGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={chartColours.blue} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={chartColours.blue} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="alertsGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={chartColours.red} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={chartColours.red} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="hour" stroke="#64748b" tick={{ fontSize: 10 }} interval={3} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="events"
                    stroke={chartColours.blue}
                    fill="url(#eventsGrad)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="alerts"
                    stroke={chartColours.red}
                    fill="url(#alertsGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Entity Risk Score Ranking */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="w-4 h-4 text-ueba-accent-purple" />
              Entity Risk Score Ranking
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={entityRiskData}
                  layout="vertical"
                  margin={{ left: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#64748b"
                    tick={{ fontSize: 10 }}
                    width={90}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                    {entityRiskData.map((entry, idx) => (
                      <Cell
                        key={idx}
                        fill={
                          entry.score >= 80
                            ? chartColours.red
                            : entry.score >= 60
                            ? chartColours.yellow
                            : chartColours.green
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Event Type Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <PieChart className="w-4 h-4 text-ueba-accent-green" />
              Event Type Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart data={stats?.event_type_distribution?.length ? stats.event_type_distribution : eventTypeData}>
                  <Pie
                    data={eventTypeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {eventTypeData.map((entry, idx) => (
                      <Cell
                        key={idx}
                        fill={
                          [
                            chartColours.blue,
                            chartColours.green,
                            chartColours.yellow,
                            chartColours.red,
                            chartColours.purple,
                            chartColours.slate,
                          ][idx]
                        }
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-1 mt-2">
              {eventTypeData.map((item, idx) => (
                <div key={item.name} className="flex items-center gap-2 text-xs">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{
                      backgroundColor: [
                        chartColours.blue,
                        chartColours.green,
                        chartColours.yellow,
                        chartColours.red,
                        chartColours.purple,
                        chartColours.slate,
                      ][idx],
                    }}
                  />
                  <span className="text-ueba-text-muted">{item.name}</span>
                  <span className="text-ueba-text-primary font-medium">{item.value}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Alert Severity Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Zap className="w-4 h-4 text-ueba-accent-red" />
              Alert Severity Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats?.alert_severity?.length ? stats.alert_severity : alertSeverityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="severity" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {alertSeverityData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {alertSeverityData.map((item) => (
                <div key={item.severity} className="flex items-center justify-between p-2 rounded bg-ueba-bg-deep">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="text-xs text-ueba-text-muted">{item.severity}</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-ueba-text-primary">{item.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top entities - system health mini-metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Shield className="w-4 h-4 text-ueba-accent-green" />
              System Health Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="status-dot active" />
                  <span className="text-xs text-ueba-text-secondary">Detection Engine</span>
                </div>
                <span className="text-xs text-ueba-accent-green font-medium">Healthy</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="status-dot active" />
                  <span className="text-xs text-ueba-text-secondary">Data Pipeline</span>
                </div>
                <span className="text-xs text-ueba-accent-green font-medium">{(stats?.events_last_hour ?? 0).toLocaleString()} evts/hr</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="status-dot warning" />
                  <span className="text-xs text-ueba-text-secondary">ML Model</span>
                </div>
                <span className="text-xs text-ueba-accent-yellow font-medium">Active</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="status-dot active" />
                  <span className="text-xs text-ueba-text-secondary">Storage</span>
                </div>
                <span className="text-xs text-ueba-accent-green font-medium">{(stats?.total_events ?? 0).toLocaleString()} events</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="status-dot warning" />
                  <span className="text-xs text-ueba-text-secondary">Alert Queue</span>
                </div>
                <span className="text-xs text-ueba-accent-yellow font-medium">{stats?.active_alerts ?? 0} pending</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="status-dot critical" />
                  <span className="text-xs text-ueba-text-secondary">Critical Alerts</span>
                </div>
                <span className="text-xs text-ueba-accent-red font-medium">{stats?.critical_alerts ?? 0}</span>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-ueba-border">
              <Button variant="outline" size="sm" className="w-full">
                View System Status
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
