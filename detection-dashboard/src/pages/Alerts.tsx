import { useState } from 'react';
import {
  Bell,
  AlertTriangle,
  Search,
  Filter,
  ChevronDown,
  ChevronUp,
  User,
  Clock,
  Activity,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { Pagination } from '@/components/ui/Pagination';
import { PageLoading } from '@/components/shared/LoadingSpinner';
import { MetricCard } from '@/components/shared/MetricCard';
import { formatTimestamp, riskScoreColor, severityColor, statusColor, truncate } from '@/lib/utils';
import type { Alert } from '@/lib/api';

// Mock data
const MOCK_ALERTS: Alert[] = [
  {
    id: 'ALT-001',
    title: 'Privilege Escalation Detected - john.doe',
    description: 'Unusual privilege escalation activity detected from user john.doe. Multiple sensitive commands executed within a short time window.',
    severity: 'critical',
    status: 'open',
    assignee: null,
    entity: 'john.doe',
    risk_score: 92,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [
      { id: 'e-001', timestamp: new Date().toISOString(), source: 'windows', entity: 'john.doe', event_type: 'privilege_escalation', risk_score: 92, details: { process: 'powershell.exe', parent: 'explorer.exe' }, raw_data: '' },
      { id: 'e-002', timestamp: new Date(Date.now() - 120000).toISOString(), source: 'windows', entity: 'john.doe', event_type: 'process_execution', risk_score: 78, details: { process: 'cmd.exe', args: '/c whoami' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-002',
    title: 'Data Exfiltration - svc-backup',
    description: 'Large outbound data transfer detected from svc-backup to an external IP address in an unfamiliar geographic region.',
    severity: 'critical',
    status: 'investigating',
    assignee: 'Sarah Connor',
    entity: 'svc-backup',
    risk_score: 88,
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
    events: [
      { id: 'e-003', timestamp: new Date(Date.now() - 3600000).toISOString(), source: 'network', entity: 'svc-backup', event_type: 'data_exfiltration', risk_score: 88, details: { destination: '185.220.101.45', bytes: '1.2GB' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-003',
    title: 'Brute Force Attempt - api-gateway',
    description: 'Multiple failed authentication attempts detected on the API gateway from a suspicious IP range.',
    severity: 'high',
    status: 'open',
    assignee: null,
    entity: 'api-gateway',
    risk_score: 76,
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
    events: [
      { id: 'e-004', timestamp: new Date(Date.now() - 7200000).toISOString(), source: 'cloud', entity: 'api-gateway', event_type: 'authentication', risk_score: 76, details: { location: 'RU', failed_attempts: 23, ip: '91.108.56.x' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-004',
    title: 'Unusual Login Time - jane.smith',
    description: 'User jane.smith authenticated from an unusual location at an atypical time (03:14 AM local time).',
    severity: 'medium',
    status: 'investigating',
    assignee: 'Mike Wilson',
    entity: 'jane.smith',
    risk_score: 65,
    created_at: new Date(Date.now() - 14400000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
    events: [
      { id: 'e-005', timestamp: new Date(Date.now() - 14400000).toISOString(), source: 'windows', entity: 'jane.smith', event_type: 'authentication', risk_score: 65, details: { location: 'Remote VPN', ip: '10.0.0.45', geo: 'NL' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-005',
    title: 'Anomalous Process Chain - devops-bot',
    description: 'DevOps bot initiated an unexpected chain of process executions not matching its baseline behavioral profile.',
    severity: 'high',
    status: 'open',
    assignee: null,
    entity: 'devops-bot',
    risk_score: 81,
    created_at: new Date(Date.now() - 21600000).toISOString(),
    updated_at: new Date(Date.now() - 21600000).toISOString(),
    events: [
      { id: 'e-006', timestamp: new Date(Date.now() - 21600000).toISOString(), source: 'linux', entity: 'devops-bot', event_type: 'process_execution', risk_score: 81, details: { process: 'kubectl', args: 'exec -- /bin/bash -c "curl...' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-006',
    title: 'Sensitive File Access - svc-backup',
    description: 'Service account accessed sensitive configuration files outside normal backup window.',
    severity: 'medium',
    status: 'resolved',
    assignee: 'Sarah Connor',
    entity: 'svc-backup',
    risk_score: 58,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 43200000).toISOString(),
    events: [
      { id: 'e-007', timestamp: new Date(Date.now() - 86400000).toISOString(), source: 'linux', entity: 'svc-backup', event_type: 'file_access', risk_score: 58, details: { file: '/etc/kubernetes/admin.conf', action: 'read' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-007',
    title: 'New SSH Key Added - mike.wilson',
    description: 'A new SSH public key was added to authorized_keys for user mike.wilson from an unrecognized host.',
    severity: 'low',
    status: 'dismissed',
    assignee: 'Mike Wilson',
    entity: 'mike.wilson',
    risk_score: 35,
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    events: [
      { id: 'e-008', timestamp: new Date(Date.now() - 172800000).toISOString(), source: 'linux', entity: 'mike.wilson', event_type: 'privilege_escalation', risk_score: 35, details: { key: 'ssh-rsa AAAA...', host: 'dev-box-02' }, raw_data: '' },
    ],
  },
  {
    id: 'ALT-008',
    title: 'Crypto Mining Detected - svc-backup',
    description: 'Potential cryptocurrency mining activity detected on svc-backup server. Unusual CPU usage pattern and network connections to known mining pools.',
    severity: 'critical',
    status: 'open',
    assignee: null,
    entity: 'svc-backup',
    risk_score: 95,
    created_at: new Date(Date.now() - 600000).toISOString(),
    updated_at: new Date(Date.now() - 600000).toISOString(),
    events: [
      { id: 'e-009', timestamp: new Date(Date.now() - 600000).toISOString(), source: 'linux', entity: 'svc-backup', event_type: 'process_execution', risk_score: 95, details: { process: 'xmrig', cpu: '98%', connections: ['pool.minexmr.com:4444'] }, raw_data: '' },
    ],
  },
];

export default function Alerts() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const severityOptions = [
    { value: '', label: 'All Severities' },
    { value: 'critical', label: 'Critical' },
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
  ];

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'open', label: 'Open' },
    { value: 'investigating', label: 'Investigating' },
    { value: 'resolved', label: 'Resolved' },
    { value: 'dismissed', label: 'Dismissed' },
  ];

  const filteredAlerts = MOCK_ALERTS.filter((alert) => {
    if (searchQuery && !alert.title.toLowerCase().includes(searchQuery.toLowerCase()) && !alert.entity.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (severityFilter && alert.severity !== severityFilter) return false;
    if (statusFilter && alert.status !== statusFilter) return false;
    return true;
  });

  const criticalCount = MOCK_ALERTS.filter((a) => a.severity === 'critical' && a.status === 'open').length;
  const openCount = MOCK_ALERTS.filter((a) => a.status === 'open').length;
  const investigatingCount = MOCK_ALERTS.filter((a) => a.status === 'investigating').length;

  const severityBadgeVariant = (severity: string): 'danger' | 'warning' | 'info' | 'success' => {
    switch (severity) {
      case 'critical': return 'danger';
      case 'high': return 'warning';
      case 'medium': return 'info';
      default: return 'success';
    }
  };

  const statusBadgeVariant = (status: string): 'danger' | 'warning' | 'success' | 'default' => {
    switch (status) {
      case 'open': return 'danger';
      case 'investigating': return 'warning';
      case 'resolved': return 'success';
      default: return 'default';
    }
  };

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Alerts"
          value={MOCK_ALERTS.length}
          accent="blue"
          icon={<Bell />}
          subtitle="All time"
        />
        <MetricCard
          title="Open"
          value={openCount}
          accent="red"
          icon={<AlertTriangle />}
          trend="up"
          trendValue="+2"
        />
        <MetricCard
          title="Investigating"
          value={investigatingCount}
          accent="yellow"
          icon={<Activity />}
          subtitle="In progress"
        />
        <MetricCard
          title="Critical Open"
          value={criticalCount}
          accent="red"
          icon={<Zap />}
          subtitle="Requires immediate action"
        />
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-ueba-text-muted mb-1">Search</label>
              <Input
                icon={<Search className="w-4 h-4" />}
                placeholder="Search alerts by title or entity..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="w-40">
              <label className="block text-xs text-ueba-text-muted mb-1">Severity</label>
              <Select
                options={severityOptions}
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
              />
            </div>
            <div className="w-40">
              <label className="block text-xs text-ueba-text-muted mb-1">Status</label>
              <Select
                options={statusOptions}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              />
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(''); setSeverityFilter(''); setStatusFilter(''); }}>
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Alert list */}
      <div className="space-y-3">
        {filteredAlerts.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Bell className="w-12 h-12 text-ueba-text-muted mb-3" />
              <h3 className="text-base font-medium text-ueba-text-primary mb-1">No Alerts Found</h3>
              <p className="text-sm text-ueba-text-muted">No alerts match your current filters</p>
            </CardContent>
          </Card>
        ) : (
          filteredAlerts.map((alert) => {
            const isExpanded = expandedId === alert.id;
            return (
              <Card key={alert.id} className="overflow-hidden">
                <div
                  className="p-4 cursor-pointer hover:bg-ueba-cardhover/30 transition-colors"
                  onClick={() => setExpandedId(isExpanded ? null : alert.id)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <div className="flex-shrink-0 mt-0.5">
                        <div className={`w-3 h-3 rounded-full ${
                          alert.severity === 'critical' ? 'bg-ueba-accent-red' :
                          alert.severity === 'high' ? 'bg-orange-500' :
                          alert.severity === 'medium' ? 'bg-ueba-accent-yellow' :
                          'bg-ueba-accent-blue'
                        }`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <h3 className="text-sm font-semibold text-ueba-text-primary">
                            {alert.title}
                          </h3>
                          <Badge variant={severityBadgeVariant(alert.severity)}>
                            {alert.severity}
                          </Badge>
                          <Badge variant={statusBadgeVariant(alert.status)}>
                            {alert.status}
                          </Badge>
                        </div>
                        <p className="text-xs text-ueba-text-muted line-clamp-1">
                          {alert.description}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 flex-shrink-0">
                      <div className="text-right hidden md:block">
                        <div className={`text-sm font-mono font-bold ${riskScoreColor(alert.risk_score)}`}>
                          {alert.risk_score}
                        </div>
                        <div className="text-[10px] text-ueba-text-muted">Risk Score</div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-ueba-text-muted" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-ueba-text-muted" />
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mt-2 text-[10px] text-ueba-text-muted">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimestamp(alert.created_at)}
                    </span>
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {alert.assignee || 'Unassigned'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Activity className="w-3 h-3" />
                      {alert.entity}
                    </span>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-ueba-border bg-ueba-bg-deep p-4 space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2">
                          Alert Details
                        </h4>
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-xs text-ueba-text-muted">ID</span>
                            <span className="text-xs text-ueba-text-secondary font-mono">{alert.id}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-ueba-text-muted">Created</span>
                            <span className="text-xs text-ueba-text-secondary">{formatTimestamp(alert.created_at)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-ueba-text-muted">Updated</span>
                            <span className="text-xs text-ueba-text-secondary">{formatTimestamp(alert.updated_at)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-ueba-text-muted">Entity</span>
                            <span className="text-xs text-ueba-text-secondary font-medium">{alert.entity}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-ueba-text-muted">Assignee</span>
                            <span className="text-xs text-ueba-text-secondary">{alert.assignee || '—'}</span>
                          </div>
                        </div>

                        <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2 mt-4">
                          Actions
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {alert.status === 'open' && (
                            <>
                              <Button size="sm" variant="outline" onClick={() => alert.status = 'investigating'}>
                                Start Investigation
                              </Button>
                              <Button size="sm" variant="ghost">
                                Assign to me
                              </Button>
                            </>
                          )}
                          {alert.status === 'investigating' && (
                            <>
                              <Button size="sm" variant="default">
                                Resolve
                              </Button>
                              <Button size="sm" variant="outline">
                                Escalate
                              </Button>
                            </>
                          )}
                          {(alert.status === 'open' || alert.status === 'investigating') && (
                            <Button size="sm" variant="destructive">
                              Dismiss
                            </Button>
                          )}
                        </div>
                      </div>

                      <div>
                        <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2">
                          Description
                        </h4>
                        <p className="text-xs text-ueba-text-secondary leading-relaxed mb-4">
                          {alert.description}
                        </p>

                        <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2">
                          Related Events ({alert.events.length})
                        </h4>
                        <div className="space-y-2">
                          {alert.events.map((event) => (
                            <div
                              key={event.id}
                              className="flex items-center justify-between p-2 rounded bg-ueba-card border border-ueba-border"
                            >
                              <div className="min-w-0">
                                <p className="text-xs text-ueba-text-primary font-medium">
                                  {event.event_type.replace(/_/g, ' ')}
                                </p>
                                <p className="text-[10px] text-ueba-text-muted">
                                  {formatTimestamp(event.timestamp)} · {event.source}
                                </p>
                              </div>
                              <span className={`text-xs font-mono font-bold ${riskScoreColor(event.risk_score)} ml-2`}>
                                {event.risk_score}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}

function Zap({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
      />
    </svg>
  );
}
