import { apiClient } from './api-client';
import { PreferencesResponse, PreferencesUpdate } from '../types/preferences';

export async function getPreferences(): Promise<PreferencesResponse> {
  return apiClient<PreferencesResponse>('/preferences');
}

export async function updatePreferences(prefs: PreferencesUpdate): Promise<PreferencesResponse> {
  return apiClient<PreferencesResponse>('/preferences', {
    method: 'PUT',
    body: JSON.stringify(prefs),
  });
}
