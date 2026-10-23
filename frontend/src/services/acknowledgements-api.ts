import { apiClient } from './api-client';
import {
  AcknowledgementCreate,
  AcknowledgementFilterParams,
  AcknowledgementItem,
  AcknowledgementListResponse,
} from '../types/acknowledgement';

export async function createAcknowledgement(data: AcknowledgementCreate): Promise<AcknowledgementItem> {
  return apiClient<AcknowledgementItem>('/acknowledgements', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getAcknowledgements(
  filters: AcknowledgementFilterParams = {}
): Promise<AcknowledgementListResponse> {
  const query = new URLSearchParams();
  if (typeof filters.event_id === 'number') query.set('event_id', filters.event_id.toString());
  if (filters.action) query.set('action', filters.action);
  if (typeof filters.limit === 'number') query.set('limit', filters.limit.toString());
  if (typeof filters.offset === 'number') query.set('offset', filters.offset.toString());

  const queryString = query.toString();
  const endpoint = `/acknowledgements${queryString ? `?${queryString}` : ''}`;
  return apiClient<AcknowledgementListResponse>(endpoint);
}
