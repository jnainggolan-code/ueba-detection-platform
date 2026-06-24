import { useState, useEffect, useCallback } from 'react';
import { Search, Users, AlertTriangle, History, Shield, Activity } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PageLoading } from '@/components/shared/LoadingSpinner';
import { MetricCard } from '@/components/shared/MetricCard';
import { formatTimestamp, riskScoreColor, truncate } from '@/lib/utils';
import { getAlerts, getEntityDetections, getStats, type DetectionEvent, type Alert, type Stats } from '@/lib/api';

interface EntitySummary {
  name: string;
  risk_score: number;
  department: string;
  events_count: number;
  anomalies: number;
  last_seen: string;
  status: 'critical' | 'warning' | 'normal';
}

export default function UserDetection() {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  // Entity detail state
  const [entityDetail, setEntityDetail] = useState<{
    risk_score: number;
    department: string;
    recent_events: DetectionEvent[];
    anomalies: { id?: string; anomaly_type?: string; severity?: string; score?: number; description?: string | null; timestamp?: string; event_type?: string; risk_score?: number }[];
    first_seen: string | null;
    last_seen: string | null;
  } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch entities from alerts + stats on mount
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [alertsResult, statsResult] = await Promise.all([
          getAlerts({ page: 1, limit: 100 }),
          getStats(),
        ]);
        setStats(statsResult);

        // Build entity list from alerts
        const entityMap = new Map<string, { risk_score: number; anomalies: number; last_seen: string }>();
        alertsResult.data.forEach((alert: Alert) => {
          const existing = entityMap.get(alert.entity);
          if (existing) {
            existing.anomalies += 1;
            existing.risk_score = Math.max(existing.risk_score, alert.risk_score);
            if (new Date(alert.created_at) > new Date(existing.last_seen)) {
              existing.last_seen = alert.created_at;
            }
          } else {
            entityMap.set(alert.entity, {
              risk_score: alert.risk_score,
              anomalies: 1,
              last_seen: alert.created_at,
            });
          }
        });

        const entityList: EntitySummary[] = Array.from(entityMap.entries()).map(([name, data]) => ({
          name,
          risk_score: data.risk_score,
          department: 'Unknown',
          events_count: 0,
          anomalies: data.anomalies,
          last_seen: data.last_seen,
          status: data.risk_score >= 70 ? 'critical' : data.risk_score >= 40 ? 'warning' : 'normal',
        }));

        setEntities(entityList);
      } catch (err) {
        console.error('Failed to fetch entity data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Fetch entity detail when selected
  useEffect(() => {
    if (!selectedEntity) {
      setEntityDetail(null);
      return;
    }
    const fetchDetail = async () => {
      setDetailLoading(true);
      setEntityDetail(null);
      try {
        const data = await getEntityDetections(selectedEntity);
        setEntityDetail({
          risk_score: data.risk_score,
          department: (data as any).department || 'Unknown',
          recent_events: data.recent_events || [],
          anomalies: data.anomalies || [],
          first_seen: (data as any).first_seen || null,
          last_seen: (data as any).last_seen || null,
        });
      } catch (err) {
        console.error(`Failed to fetch entity detail for ${selectedEntity}`, err);
      } finally {
        setDetailLoading(false);
      }
    };
    fetchDetail();
  }, [selectedEntity]);

  const filteredEntities = entities.filter((e) =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const statusConfig = {
    critical: { color: 'text-ueba-accent-red', bg: 'bg-red-500/10', dot: 'bg-ueba-accent-red' },
    warning: { color: 'text-ueba-accent-yellow', bg: 'bg-yellow-500/10', dot: 'bg-ueba-accent-yellow' },
    normal: { color: 'text-ueba-accent-green', bg: 'bg-emerald-500/10', dot: 'bg-ueba-accent-green' },
  };

  if (loading) {
    return <PageLoading />;
  }

  return (
    <div className="space-y-6">
      {/* Summary cards — from API */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Total Entities" value={entities.length} accent="blue" icon={<Users />} subtitle="Monitored entities" />
        <MetricCard
          title="At Risk"
          value={entities.filter((e) => e.status !== 'normal').length}
          accent="red"
          icon={<AlertTriangle />}
          trend="up"
          trendValue="+"
        />
        <MetricCard
          title="Anomalies Detected"
          value={entities.reduce((sum, e) => sum + e.anomalies, 0)}
          accent="yellow"
          icon={<Activity />}
          subtitle="Total anomalies"
        />
        <MetricCard
          title="Avg Risk Score"
          value={entities.length > 0 ? (entities.reduce((sum, e) => sum + e.risk_score, 0) / entities.length).toFixed(0) : '0'}
          accent="green"
          icon={<Shield />}
          trend="up"
          trendValue="-"
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
          {selectedEntity && entityDetail ? (
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
                        <h2 className="text-lg font-bold text-ueba-text-primary">{selectedEntity}</h2>
                        <p className="text-xs text-ueba-text-muted">
                          {entityDetail.department} · {entityDetail.recent_events.length + entityDetail.anomalies.length} events
                        </p>
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
                    <Badge variant={entityDetail.risk_score >= 70 ? 'danger' : entityDetail.risk_score >= 40 ? 'warning' : 'success'}>
                      {entityDetail.risk_score >= 70 ? 'critical' : entityDetail.risk_score >= 40 ? 'warning' : 'normal'}
                    </Badge>
                    <Badge variant="info">{entityDetail.department}</Badge>
                    <Badge variant="default">{entityDetail.anomalies.length} anomalies</Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 mt-3 text-[10px] text-ueba-text-muted">
                    {entityDetail.first_seen && (
                      <span>First seen: {new Date(entityDetail.first_seen).toLocaleDateString()}</span>
                    )}
                    {entityDetail.last_seen && (
                      <span>Last seen: {new Date(entityDetail.last_seen).toLocaleDateString()}</span>
                    )}
                    {!entityDetail.first_seen && !entityDetail.last_seen && (
                      <span>Tracking since recent detection</span>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Anomaly markers */}
              {entityDetail.anomalies.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-ueba-accent-red" />
                      Anomaly Markers
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {entityDetail.anomalies.map((anomaly, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded bg-ueba-bg-deep border border-ueba-border">
                          <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${anomaly.severity === 'critical' ? 'bg-ueba-accent-red' : anomaly.severity === 'high' ? 'bg-orange-500' : 'bg-ueba-accent-yellow'}`} />
                            <div>
                              <p className="text-xs text-ueba-text-primary font-medium">
                                {(anomaly.anomaly_type || anomaly.event_type || "unknown").replace(/_/g, " ")}
                              </p>
                              <p className="text-[10px] text-ueba-text-muted">{anomaly.description || anomaly.timestamp}</p>
                            </div>
                          </div>
                          <span className={`text-xs font-mono font-bold ${riskScoreColor((anomaly.score || anomaly.risk_score || 0) * 10)}`}>
                            {Math.round((anomaly.score || anomaly.risk_score || 0) * 10)}
                          </span>
                        </div>
                      ))}
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
                    {entityDetail.recent_events.length > 0 ? (
                      entityDetail.recent_events.map((event) => (
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
                      ))
                    ) : (
                      <p className="text-xs text-ueba-text-muted text-center py-4">
                        No recent events for this entity
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : selectedEntity && detailLoading ? (
            <PageLoading />
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
