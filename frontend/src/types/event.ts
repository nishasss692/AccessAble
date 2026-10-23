/**
 * Schema types for Event entity matching backend FastAPI schemas.
 */

export interface EventMetadata {
  battery?: number;
  motion_score?: number;
  zone?: string;
  duration_seconds?: number;
  [key: string]: unknown;
}

export interface EventItem {
  id: number;
  source: 'ring' | 'demo' | string;
  external_event_id: string | null;
  event_type: 'motion' | 'doorbell_ring' | 'doorbell_press' | 'chime' | string;
  occurred_at: string; // ISO UTC string
  device_id: string | null;
  metadata: EventMetadata;
  received_at: string; // ISO UTC string
}

export interface EventCreate {
  source: 'ring' | 'demo' | string;
  external_event_id?: string | null;
  event_type: string;
  occurred_at: string;
  device_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface EventIngestionResponse {
  event: EventItem;
  is_duplicate: boolean;
}

export interface EventListResponse {
  items: EventItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EventFilterParams {
  source?: string;
  event_type?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}
