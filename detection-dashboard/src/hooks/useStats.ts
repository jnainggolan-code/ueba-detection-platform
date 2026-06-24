import { useState, useEffect, useCallback } from 'react';
import { getStats, type Stats } from '@/lib/api';

export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getStats();
      setStats(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats,
  };
}

export function useMockStats(): Stats {
  return {
    total_events: 154283,
    active_alerts: 47,
    entities_at_risk: 23,
    avg_risk_score: 42,
    events_last_hour: 3891,
    critical_alerts: 12,
  };
}
