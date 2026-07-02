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
  // Track cursor stack for Prev navigation
  const [cursorStack, setCursorStack] = useState<string[]>([]);

  const fetchEvents = useCallback(async (q: EventsQuery) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getEvents(q);
      setData(result);
      return result;
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
    // Reset pagination state when filters change
    setCursorStack([]);
    setQuery((prev) => ({
      ...prev,
      ...updates,
      page: updates.page ?? 1,
      cursor: undefined, // Clear cursor when filters change
    }));
  };

  const goToPage = (page: number) => {
    // Page-based navigation (backward compat)
    setCursorStack([]);
    setQuery((prev) => ({ ...prev, page, cursor: undefined }));
  };

  const goNext = () => {
    if (!data?.cursor) return;
    // Push current cursor onto stack for Prev support
    const prevCursor = query.cursor;
    if (prevCursor) {
      setCursorStack((stack) => [...stack, prevCursor]);
    }
    setQuery((prev) => ({ ...prev, cursor: data.cursor, page: undefined }));
  };

  const goPrev = () => {
    if (cursorStack.length === 0) return;
    const prevCursor = cursorStack[cursorStack.length - 1];
    setCursorStack((stack) => stack.slice(0, -1));
    setQuery((prev) => ({ ...prev, cursor: prevCursor, page: undefined }));
  };

  return {
    events: data?.data ?? [],
    total: data?.total ?? 0,
    totalPages: data?.total_pages ?? 0,
    currentPage: data?.page ?? 1,
    hasMore: data?.has_more ?? false,
    hasPrev: cursorStack.length > 0,
    loading,
    error,
    query,
    updateQuery,
    goToPage,
    goNext,
    goPrev,
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
