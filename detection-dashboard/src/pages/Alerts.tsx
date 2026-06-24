import { useState, useEffect } from 'react';
import { Bell, AlertTriangle, Search, Activity, Clock, User, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { Pagination } from '@/components/ui/Pagination';
import { PageLoading } from '@/components/shared/LoadingSpinner';
import { MetricCard } from '@/components/shared/MetricCard';
import { formatTimestamp, riskScoreColor } from '@/lib/utils';
import { useAlerts } from '@/hooks/useAlerts';
import { getAlertCounts } from '@/lib/api';
import type { AlertCounts } from '@/lib/api';

function Zap({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

export default function Alerts() {
  const {
    alerts,
    total,
    totalPages,
    currentPage,
    loading,
    error,
    filters,
    updateFilters,
    goToPage,
    updateStatus,
    refetch,
  } = useAlerts();

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [counts, setCounts] = useState<AlertCounts | null>(null);

  useEffect(() => {
    getAlertCounts()
      .then(setCounts)
      .catch((err) => console.error('Failed to fetch alert counts', err));
  }, []);

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

  // Local filter for search (UI-side only since backend may not support search)
  const filteredAlerts = alerts.filter((alert) => {
    if (searchQuery && !alert.title.toLowerCase().includes(searchQuery.toLowerCase()) && !alert.entity.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const criticalCount = counts?.critical_open ?? filteredAlerts.filter((a) => a.severity === 'critical' && a.status === 'open').length;
  const openCount = counts?.open ?? filteredAlerts.filter((a) => a.status === 'open').length;
  const investigatingCount = counts?.investigating ?? filteredAlerts.filter((a) => a.status === 'investigating').length;

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

  if (loading && alerts.length === 0) {
    return <PageLoading />;
  }

  return (
    <div className="space-y-6">
      {/* Stats row — from /alerts/counts API */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Total Alerts" value={counts?.total ?? total} accent="blue" icon={<Bell />} subtitle="All time" />
        <MetricCard title="Open" value={openCount} accent="red" icon={<AlertTriangle />} trend="up" trendValue="+" />
        <MetricCard title="Investigating" value={investigatingCount} accent="yellow" icon={<Activity />} subtitle="In progress" />
        <MetricCard title="Critical Open" value={criticalCount} accent="red" icon={<Zap />} subtitle="Requires immediate action" />
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
                value={filters.severity ?? ''}
                onChange={(e) => updateFilters({ severity: e.target.value })}
              />
            </div>
            <div className="w-40">
              <label className="block text-xs text-ueba-text-muted mb-1">Status</label>
              <Select
                options={statusOptions}
                value={filters.status ?? ''}
                onChange={(e) => updateFilters({ status: e.target.value })}
              />
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(''); updateFilters({ severity: '', status: '' }); }}>
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
                            <span className="text-xs text-ueba-text-secondary">{alert.assignee || '\u2014'}</span>
                          </div>
                        </div>

                        <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2 mt-4">
                          Actions
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {alert.status === 'open' && (
                            <>
                              <Button size="sm" variant="outline" onClick={() => updateStatus(alert.id.replace('ALT-', ''), 'investigating')}>
                                Start Investigation
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => updateStatus(alert.id.replace('ALT-', ''), 'investigating', 'Current User')}>
                                Assign to me
                              </Button>
                            </>
                          )}
                          {alert.status === 'investigating' && (
                            <>
                              <Button size="sm" variant="default" onClick={() => updateStatus(alert.id.replace('ALT-', ''), 'resolved')}>
                                Resolve
                              </Button>
                              <Button size="sm" variant="outline">
                                Escalate
                              </Button>
                            </>
                          )}
                          {(alert.status === 'open' || alert.status === 'investigating') && (
                            <Button size="sm" variant="destructive" onClick={() => updateStatus(alert.id.replace('ALT-', ''), 'dismissed')}>
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

                        {alert.events.length > 0 && (
                          <>
                            <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2">
                              Related Events ({alert.events.length})
                            </h4>
                            <div className="space-y-2">
                              {alert.events.slice(0, 5).map((event) => (
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
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={goToPage}
          />
        </div>
      )}
    </div>
  );
}
