import { apiClient } from './api-client';
import { EventCreate, EventFilterParams, EventIngestionResponse, EventListResponse } from '../types/event';

export async function getEvents(filters: EventFilterParams = {}): Promise<EventListResponse> {
  const query = new URLSearchParams();
  if (filters.source) query.set('source', filters.source);
  if (filters.event_type) query.set('event_type', filters.event_type);
  if (filters.start_time) query.set('start_time', filters.start_time);
  if (filters.end_time) query.set('end_time', filters.end_time);
  if (typeof filters.limit === 'number') query.set('limit', filters.limit.toString());
  if (typeof filters.offset === 'number') query.set('offset', filters.offset.toString());

  const queryString = query.toString();
  const endpoint = `/events${queryString ? `?${queryString}` : ''}`;
  return apiClient<EventListResponse>(endpoint);
}

export async function createEvent(event: EventCreate): Promise<EventIngestionResponse> {
  return apiClient<EventIngestionResponse>('/events', {
    method: 'POST',
    body: JSON.stringify(event),
  });
}
