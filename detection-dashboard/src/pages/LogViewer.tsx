import { useState, useMemo, useEffect, Fragment } from 'react';
import { Search, Filter, AlertTriangle } from 'lucide-react';
import { useEvents } from '@/hooks/useEvents';
import { useStats } from '@/hooks/useStats';
import api from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { Pagination } from '@/components/ui/Pagination';
import { PageLoading, InlineLoading } from '@/components/shared/LoadingSpinner';
import { formatTimestamp, riskScoreColor, truncate } from '@/lib/utils';
import type { DetectionEvent } from '@/lib/api';

type SortField = 'timestamp' | 'risk_score';
type SortDir = 'asc' | 'desc';

export default function LogViewer() {
  const { events, total, totalPages, currentPage, loading, error, query, updateQuery, goToPage } = useEvents({ page: 1, limit: 25 });
  const [searchInput, setSearchInput] = useState('');
  const [selectedEvent, setSelectedEvent] = useState<DetectionEvent | null>(null);
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const { stats } = useStats();
  useEffect(() => {
    if (stats?.by_source) {
      setSourceOptions([
        { value: '', label: 'All Sources' },
        ...stats.by_source.map((s: any) => ({ value: s.source, label: s.source.charAt(0).toUpperCase() + s.source.slice(1) }))
      ]);
    }
    // Build event type options from recent events
    const fetchTypes = async () => {
      try {
        const res = await api.get('/v1/events', { params: { limit: 500 } });
        const types = new Set(res.data.data.map((e: any) => e.event_type).filter(Boolean));
        setEventTypeOptions([
          { value: '', label: 'All Events' },
          ...Array.from(types).map((t: any) => ({
            value: t,
            label: t.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
          }))
        ]);
      } catch {}
    };
    fetchTypes();
  }, [stats]);

  const handleSearch = () => {
    updateQuery({ search: searchInput || undefined, page: 1 });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  // Derive source options from real API data
  const [sourceOptions, setSourceOptions] = useState<{value: string; label: string}[]>([{value: '', label: 'All Sources'}]);
  const [eventTypeOptions, setEventTypeOptions] = useState<{value: string; label: string}[]>([{value: '', label: 'All Events'}]);



  // Sort events
  const sortedEvents = useMemo(() => {
    const sorted = [...events].sort((a, b) => {
      let cmp: number;
      if (sortField === 'timestamp') {
        cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      } else {
        cmp = a.risk_score - b.risk_score;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [events, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="text-ueba-text-muted ml-1">{'\u2195'}</span>;
    return <span className="text-ueba-accent-blue ml-1">{sortDir === 'asc' ? '\u2191' : '\u2193'}</span>;
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-12 h-12 text-ueba-accent-red" />
        <p className="text-ueba-accent-red font-medium">{error}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  if (loading && !events.length) {
    return <PageLoading />;
  }

  return (
    <div className="space-y-4">
      {/* Filters bar */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-ueba-text-muted mb-1">Search</label>
              <Input
                icon={<Search className="w-4 h-4" />}
                placeholder="Search by entity, source, details..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <div className="w-40">
              <label className="block text-xs text-ueba-text-muted mb-1">Source</label>
              <Select
                options={sourceOptions}
                value={query.source ?? ''}
                onChange={(e) => updateQuery({ source: e.target.value || undefined, page: 1 })}
              />
            </div>
            <div className="w-44">
              <label className="block text-xs text-ueba-text-muted mb-1">Event Type</label>
              <Select
                options={eventTypeOptions}
                value={query.event_type ?? ''}
                onChange={(e) => updateQuery({ event_type: e.target.value || undefined, page: 1 })}
              />
            </div>
            <div className="w-40">
              <label className="block text-xs text-ueba-text-muted mb-1">Entity</label>
              <Input
                placeholder="Filter by entity..."
                value={query.entity ?? ''}
                onChange={(e) => updateQuery({ entity: e.target.value || undefined, page: 1 })}
              />
            </div>
            <Button onClick={handleSearch} size="md">
              <Filter className="w-4 h-4 mr-1" />
              Apply
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results info */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-ueba-text-muted">
          Showing <span className="text-ueba-text-primary font-medium">{events.length}</span> of{' '}
          <span className="text-ueba-text-primary font-medium">{total.toLocaleString()}</span> events
        </p>
      </div>

      {/* Events table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-ueba-border bg-ueba-bg-deep/50">
                <th className="text-left text-xs font-medium text-ueba-text-muted px-4 py-3">
                  <button onClick={() => toggleSort('timestamp')} className="flex items-center hover:text-ueba-text-primary">
                    Timestamp <SortIcon field="timestamp" />
                  </button>
                </th>
                <th className="text-left text-xs font-medium text-ueba-text-muted px-4 py-3">Source</th>
                <th className="text-left text-xs font-medium text-ueba-text-muted px-4 py-3">Entity</th>
                <th className="text-left text-xs font-medium text-ueba-text-muted px-4 py-3">Event Type</th>
                <th className="text-left text-xs font-medium text-ueba-text-muted px-4 py-3">
                  <button onClick={() => toggleSort('risk_score')} className="flex items-center hover:text-ueba-text-primary">
                    Risk Score <SortIcon field="risk_score" />
                  </button>
                </th>
                <th className="text-left text-xs font-medium text-ueba-text-muted px-4 py-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ueba-border">
              {sortedEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-ueba-text-muted text-sm">
                    No events found matching your filters
                  </td>
                </tr>
              ) : (
                sortedEvents.map((event) => (
                  <Fragment key={event.id}>
                    <tr
                      className="hover:bg-ueba-cardhover/50 transition-colors cursor-pointer"
                      onClick={() => setSelectedEvent(selectedEvent?.id === event.id ? null : event)}
                    >
                      <td className="px-4 py-3">
                        <span className="text-xs text-ueba-text-secondary font-mono">
                          {formatTimestamp(event.timestamp)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="info">{event.source}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-ueba-text-primary font-medium">{event.entity}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-ueba-text-secondary">{event.event_type.replace(/_/g, ' ')}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-mono font-bold ${riskScoreColor(event.risk_score)}`}>
                          {event.risk_score.toFixed(0)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-ueba-text-muted">
                          {truncate(JSON.stringify(event.details), 60)}
                        </span>
                      </td>
                    </tr>
                    {selectedEvent?.id === event.id && (
                      <tr className="bg-ueba-bg-deep">
                        <td colSpan={6} className="px-4 py-4 border-t border-ueba-border">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2">
                                Event Details
                              </h4>
                              <div className="space-y-2">
                                <div className="flex justify-between">
                                  <span className="text-xs text-ueba-text-muted">ID</span>
                                  <span className="text-xs text-ueba-text-secondary font-mono">{event.id}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-xs text-ueba-text-muted">Timestamp</span>
                                  <span className="text-xs text-ueba-text-secondary">{formatTimestamp(event.timestamp)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-xs text-ueba-text-muted">Source</span>
                                  <span className="text-xs text-ueba-text-secondary">{event.source}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-xs text-ueba-text-muted">Entity</span>
                                  <span className="text-xs text-ueba-text-secondary">{event.entity}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-xs text-ueba-text-muted">Event Type</span>
                                  <span className="text-xs text-ueba-text-secondary">{event.event_type}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-xs text-ueba-text-muted">Risk Score</span>
                                  <span className={`text-xs font-mono font-bold ${riskScoreColor(event.risk_score)}`}>
                                    {event.risk_score.toFixed(1)}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold text-ueba-text-muted uppercase tracking-wider mb-2">
                                Raw Data
                              </h4>
                              <pre className="bg-ueba-card border border-ueba-border rounded p-3 text-xs text-ueba-text-secondary font-mono overflow-x-auto max-h-48">
                                {JSON.stringify(event.details, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="border-t border-ueba-border p-4">
          <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={goToPage} />
        </div>
      </Card>
    </div>
  );
}
