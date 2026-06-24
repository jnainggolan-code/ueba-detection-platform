import { useState, useEffect, useCallback } from 'react';
import {
  getEvents,
  getEventById,
  type DetectionEvent,
  type EventsQuery,
  type PaginatedResponse,
} from '@/lib/api';

export function useEvents(initialQuery?: EventsQuery) {
  const [data, setData] = useState<PaginatedResponse<DetectionEvent> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<EventsQuery>(initialQuery ?? { page: 1, limit: 25 });

  const fetchEvents = useCallback(async (q: EventsQuery) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getEvents(q);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch events');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents(query);
  }, [query, fetchEvents]);

  const refetch = () => fetchEvents(query);

  const updateQuery = (updates: Partial<EventsQuery>) => {
    setQuery((prev) => ({ ...prev, ...updates, page: updates.page ?? 1 }));
  };

  const goToPage = (page: number) => {
    setQuery((prev) => ({ ...prev, page }));
  };

  return {
    events: data?.data ?? [],
    total: data?.total ?? 0,
    totalPages: data?.total_pages ?? 0,
    currentPage: data?.page ?? 1,
    loading,
    error,
    query,
    updateQuery,
    goToPage,
    refetch,
  };
}

export function useEvent(id: string | undefined) {
  const [event, setEvent] = useState<DetectionEvent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getEventById(id)
      .then(setEvent)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to fetch event'))
      .finally(() => setLoading(false));
  }, [id]);

  return { event, loading, error };
}
