/**
 * Schema types for Event Acknowledgements matching backend FastAPI schemas.
 */

import { EventItem } from './event';

export type ActionType = 'acknowledged' | 'dismissed';

export interface AcknowledgementCreate {
  event_id: number;
  action: ActionType;
  note?: string | null;
}

export interface AcknowledgementItem {
  id: number;
  event_id: number;
  action: ActionType;
  note: string | null;
  acknowledged_at: string; // ISO UTC string
  event?: EventItem | null;
}

export interface AcknowledgementListResponse {
  items: AcknowledgementItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AcknowledgementFilterParams {
  event_id?: number;
  action?: ActionType;
  limit?: number;
  offset?: number;
}
