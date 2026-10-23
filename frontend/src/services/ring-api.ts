import { apiClient, API_V1 } from './api-client';
import { RingStatusResponse } from '../types/preferences';

export async function getRingStatus(): Promise<RingStatusResponse> {
  return apiClient<RingStatusResponse>('/integrations/ring/status');
}

export async function checkBackendHealth(): Promise<{ status: string; timestamp?: string }> {
  try {
    return await apiClient<{ status: string; timestamp?: string }>('/health');
  } catch {
    return { status: 'offline' };
  }
}
