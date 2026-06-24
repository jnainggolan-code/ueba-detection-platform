import { useState, useEffect, useCallback } from 'react';
import {
  getAlerts,
  getAlertById,
  updateAlertStatus,
  type Alert,
  type PaginatedResponse,
} from '@/lib/api';

export function useAlerts(initialPage = 1) {
  const [data, setData] = useState<PaginatedResponse<Alert> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(initialPage);
  const [filters, setFilters] = useState<{ severity?: string; status?: string }>({});

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getAlerts({ page, limit: 20, ...filters });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const updateFilters = (updates: { severity?: string; status?: string }) => {
    setFilters((prev) => ({ ...prev, ...updates }));
    setPage(1);
  };

  const goToPage = (p: number) => setPage(p);

  const updateStatus = async (id: string, status: Alert['status'], assignee?: string) => {
    try {
      await updateAlertStatus(id, status, assignee);
      await fetchAlerts();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update alert');
    }
  };

  return {
    alerts: data?.data ?? [],
    total: data?.total ?? 0,
    totalPages: data?.total_pages ?? 0,
    currentPage: data?.page ?? 1,
    loading,
    error,
    filters,
    updateFilters,
    goToPage,
    updateStatus,
    refetch: fetchAlerts,
  };
}

export function useAlert(id: string | undefined) {
  const [alert, setAlert] = useState<Alert | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getAlertById(id)
      .then(setAlert)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to fetch alert'))
      .finally(() => setLoading(false));
  }, [id]);

  return { alert, loading, error };
}
