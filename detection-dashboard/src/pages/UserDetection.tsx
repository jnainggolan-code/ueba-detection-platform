import { useState } from 'react';
import { Search, Users, AlertTriangle, History, Shield, Activity } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoading } from '@/components/shared/LoadingSpinner';
import { MetricCard } from '@/components/shared/MetricCard';
import { formatTimestamp, riskScoreColor, truncate } from '@/lib/utils';
import type { DetectionEvent } from '@/lib/api';

// Mock data — API will connect in Phase 2
const MOCK_ENTITIES = [
  { name: 'john.doe', risk_score: 87, department: 'Engineering', events_count: 1243, anomalies: 5, last_seen: new Date().toISOString(), status: 'critical' as const },
  { name: 'jane.smith', risk_score: 65, department: 'Finance', events_count: 876, anomalies: 2, last_seen: new Date().toISOString(), status: 'warning' as const },
  { name: 'svc-backup', risk_score: 92, department: 'System', events_count: 3402, anomalies: 8, last_seen: new Date().toISOString(), status: 'critical' as const },
  { name: 'mike.wilson', risk_score: 34, department: 'HR', events_count: 456, anomalies: 0, last_seen: new Date(Date.now() - 86400000).toISOString(), status: 'normal' as const },
  { name: 'api-gateway', risk_score: 78, department: 'Infrastructure', events_count: 8901, anomalies: 3, last_seen: new Date().toISOString(), status: 'warning' as const },
  { name: 'sarah.connor', risk_score: 45, department: 'Security', events_count: 678, anomalies: 1, last_seen: new Date(Date.now() - 3600000).toISOString(), status: 'normal' as const },
  { name: 'db-readonly', risk_score: 22, department: 'Database', events_count: 2341, anomalies: 0, last_seen: new Date(Date.now() - 7200000).toISOString(), status: 'normal' as const },
  { name: 'devops-bot', risk_score: 81, department: 'DevOps', events_count: 5621, anomalies: 4, last_seen: new Date().toISOString(), status: 'critical' as const },
];

const MOCK_RECENT_EVENTS: DetectionEvent[] = [
  { id: 'e-001', timestamp: new Date().toISOString(), source: 'windows', entity: 'john.doe', event_type: 'privilege_escalation', risk_score: 92, details: { process: 'powershell.exe', parent: 'explorer.exe', user: 'john.doe', command_line: '-EncodedCommand SQBFAFgA' }, raw_data: '' },
  { id: 'e-002', timestamp: new Date(Date.now() - 60000).toISOString(), source: 'network', entity: 'svc-backup', event_type: 'data_exfiltration', risk_score: 88, details: { destination: '185.220.101.x', bytes: '1.2GB', protocol: 'SFTP', port: 22 }, raw_data: '' },
  { id: 'e-003', timestamp: new Date(Date.now() - 180000).toISOString(), source: 'cloud', entity: 'api-gateway', event_type: 'authentication', risk_score: 72, details: { location: 'RU', failed_attempts: 23, ip: '91.108.56.x', method: 'API_KEY' }, raw_data: '' },
];

export default function UserDetection() {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEntities = MOCK_ENTITIES.filter((e) =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const entityDetail = selectedEntity
    ? MOCK_ENTITIES.find((e) => e.name === selectedEntity)
    : null;

  const statusConfig = {
    critical: { color: 'text-ueba-accent-red', bg: 'bg-red-500/10', dot: 'bg-ueba-accent-red' },
    warning: { color: 'text-ueba-accent-yellow', bg: 'bg-yellow-500/10', dot: 'bg-ueba-accent-yellow' },
    normal: { color: 'text-ueba-accent-green', bg: 'bg-emerald-500/10', dot: 'bg-ueba-accent-green' },
  };

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Entities"
          value={MOCK_ENTITIES.length}
          accent="blue"
          icon={<Users />}
          subtitle="Monitored entities"
        />
        <MetricCard
          title="At Risk"
          value={MOCK_ENTITIES.filter((e) => e.status !== 'normal').length}
          accent="red"
          icon={<AlertTriangle />}
          trend="up"
          trendValue="+3 from yesterday"
        />
        <MetricCard
          title="Anomalies Detected"
          value={MOCK_ENTITIES.reduce((sum, e) => sum + e.anomalies, 0)}
          accent="yellow"
          icon={<Activity />}
          subtitle="Last 24 hours"
        />
        <MetricCard
          title="Avg Risk Score"
          value={(MOCK_ENTITIES.reduce((sum, e) => sum + e.risk_score, 0) / MOCK_ENTITIES.length).toFixed(0)}
          accent="green"
          icon={<Shield />}
          trend="up"
          trendValue="+5.2"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Entity list */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-sm font-semibold text-ueba-text-primary">Entities</h2>
          <Input
            icon={<Search className="w-4 h-4" />}
            placeholder="Search entities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {filteredEntities.map((entity) => {
              const sc = statusConfig[entity.status];
              return (
                <Card
                  key={entity.name}
                  hover
                  className={selectedEntity === entity.name ? 'border-ueba-accent-blue' : ''}
                  onClick={() => setSelectedEntity(entity.name)}
                >
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block w-2 h-2 rounded-full ${sc.dot}`} />
                        <span className="text-sm font-medium text-ueba-text-primary">{entity.name}</span>
                      </div>
                      <span className={`text-xs font-mono font-bold ${riskScoreColor(entity.risk_score)}`}>
                        {entity.risk_score}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-ueba-text-muted">
                      <span>{entity.department}</span>
                      <span>{entity.anomalies} anomalies</span>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Entity detail view */}
        <div className="lg:col-span-2 space-y-4">
          {entityDetail ? (
            <>
              {/* Entity header */}
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-ueba-accent-red/20 to-ueba-accent-blue/20 flex items-center justify-center">
                        <Users className="w-6 h-6 text-ueba-accent-blue" />
                      </div>
                      <div>
                        <h2 className="text-lg font-bold text-ueba-text-primary">{entityDetail.name}</h2>
                        <p className="text-xs text-ueba-text-muted">{entityDetail.department} · {entityDetail.events_count.toLocaleString()} events</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-3xl font-bold font-mono ${riskScoreColor(entityDetail.risk_score)}`}>
                        {entityDetail.risk_score}
                      </div>
                      <div className="text-xs text-ueba-text-muted">Risk Score</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant={entityDetail.status === 'critical' ? 'danger' : entityDetail.status === 'warning' ? 'warning' : 'success'}>
                      {entityDetail.status}
                    </Badge>
                    <Badge variant="info">{entityDetail.department}</Badge>
                    <Badge variant="default">{entityDetail.anomalies} anomalies</Badge>
                  </div>
                </CardContent>
              </Card>

              {/* Anomaly markers */}
              {entityDetail.anomalies > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-ueba-accent-red" />
                      Anomaly Markers
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {MOCK_RECENT_EVENTS.filter((e) => e.entity === entityDetail.name).length > 0 ? (
                        MOCK_RECENT_EVENTS.filter((e) => e.entity === entityDetail.name).map((event) => (
                          <div key={event.id} className="flex items-center justify-between p-2 rounded bg-ueba-bg-deep border border-ueba-border">
                            <div className="flex items-center gap-3">
                              <div className={`w-2 h-2 rounded-full ${event.risk_score >= 80 ? 'bg-ueba-accent-red' : 'bg-ueba-accent-yellow'}`} />
                              <div>
                                <p className="text-xs text-ueba-text-primary font-medium">
                                  {event.event_type.replace(/_/g, ' ')}
                                </p>
                                <p className="text-[10px] text-ueba-text-muted">{formatTimestamp(event.timestamp)}</p>
                              </div>
                            </div>
                            <span className={`text-xs font-mono font-bold ${riskScoreColor(event.risk_score)}`}>
                              {event.risk_score}
                            </span>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-ueba-text-muted text-center py-2">
                          Recent events for this entity will appear here
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Recent events */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <History className="w-4 h-4 text-ueba-accent-blue" />
                    Recent Events
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {MOCK_RECENT_EVENTS.map((event) => (
                      <div key={event.id} className="flex items-center justify-between p-3 rounded bg-ueba-bg-deep border border-ueba-border">
                        <div className="flex items-center gap-3 min-w-0">
                          <Badge variant="info">{event.source}</Badge>
                          <div className="min-w-0">
                            <p className="text-xs text-ueba-text-primary font-medium truncate">
                              {event.event_type.replace(/_/g, ' ')}
                            </p>
                            <p className="text-[10px] text-ueba-text-muted">{truncate(JSON.stringify(event.details), 40)}</p>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0 ml-2">
                          <span className={`text-xs font-mono font-bold ${riskScoreColor(event.risk_score)}`}>
                            {event.risk_score}
                          </span>
                          <p className="text-[10px] text-ueba-text-muted">{formatTimestamp(event.timestamp)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-16">
                <Users className="w-16 h-16 text-ueba-text-muted mb-4" />
                <h3 className="text-lg font-medium text-ueba-text-primary mb-1">Select an Entity</h3>
                <p className="text-sm text-ueba-text-muted text-center max-w-md">
                  Choose an entity from the list to view their risk score, anomaly markers, and recent events
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
