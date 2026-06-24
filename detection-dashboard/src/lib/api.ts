import axios from 'axios';

const api = axios.create({
  baseURL: "/api",
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(`API Error ${error.response.status}:`, error.response.data);
    } else if (error.request) {
      console.error('API Network Error: No response received', error.message);
    } else {
      console.error('API Request Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// ---- Types ----

export interface DetectionEvent {
  id: string;
  timestamp: string;
  source: string;
  entity: string;
  event_type: string;
  risk_score: number;
  details: Record<string, unknown>;
  raw_data: string;
}

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'open' | 'investigating' | 'resolved' | 'dismissed';
  assignee: string | null;
  entity: string;
  risk_score: number;
  created_at: string;
  updated_at: string;
  events: DetectionEvent[];
}

export interface AlertCounts {
  total: number;
  open: number;
  investigating: number;
  resolved: number;
  dismissed: number;
  critical_open: number;
  high_open: number;
}

export interface Stats {
  total_events: number;
  active_alerts: number;
  entities_at_risk: number;
  avg_risk_score: number;
  events_last_hour: number;
  critical_alerts: number;
  /** Chart data */
  event_trend?: { hour: string; events: number; alerts: number }[];
  entity_risk?: { name: string; score: number }[];
  event_type_distribution?: { name: string; value: number }[];
  alert_severity?: { severity: string; count: number; color: string }[];
  health_status?: { label: string; status: string; value: string }[];
}

export interface EventsQuery {
  page?: number;
  limit?: number;
  source?: string;
  entity?: string;
  event_type?: string;
  search?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// ---- Event APIs ----

export const getEvents = (params?: EventsQuery): Promise<PaginatedResponse<DetectionEvent>> =>
  api.get('/v1/events', { params }).then((res) => res.data);

export const getEventById = (id: string): Promise<DetectionEvent> =>
  api.get(`/v1/events/${id}`).then((res) => res.data);

// ---- Alert APIs ----

export const getAlerts = (params?: {
  page?: number;
  limit?: number;
  severity?: string;
  status?: string;
}): Promise<PaginatedResponse<Alert>> =>
  api.get('/v1/alerts', { params }).then((res) => res.data);

export const getAlertById = (id: string): Promise<Alert> =>
  api.get(`/v1/alerts/${id}`).then((res) => res.data);

export const updateAlertStatus = (
  id: string,
  status: Alert['status'],
  assignee?: string
): Promise<Alert> =>
  api.patch(`/v1/alerts/${id}`, { status, assignee }).then((res) => res.data);

export const getAlertCounts = (): Promise<AlertCounts> =>
  api.get('/v1/alerts/counts').then((res) => res.data);

// ---- Stats APIs ----

export const getStats = (timeRange: string = '24h'): Promise<Stats> =>
  api.get('/v1/stats', { params: { time_range: timeRange } }).then((res) => res.data);

// ---- Entity APIs ----

export const getEntityDetections = (
  entity: string
): Promise<{ risk_score: number; recent_events: DetectionEvent[]; anomalies: DetectionEvent[] }> =>
  api.get(`/v1/entities/${encodeURIComponent(entity)}`).then((res) => res.data);

export default api;
