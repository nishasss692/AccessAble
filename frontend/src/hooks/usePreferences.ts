import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { getPreferences, updatePreferences } from '../services/preferences-api';
import { PreferencesResponse, PreferencesUpdate } from '../types/preferences';

export function usePreferences() {
  const queryClient = useQueryClient();

  const preferencesQuery = useQuery<PreferencesResponse>({
    queryKey: ['preferences'],
    queryFn: getPreferences,
  });

  const updateMutation = useMutation({
    mutationFn: (newPrefs: PreferencesUpdate) => updatePreferences(newPrefs),
    onSuccess: (data) => {
      queryClient.setQueryData(['preferences'], data);
    },
  });

  // Apply preferences directly to DOM document and body
  useEffect(() => {
    if (!preferencesQuery.data) return;
    const { high_contrast_enabled, text_scale } = preferencesQuery.data;

    // Apply high-contrast class to document body
    if (high_contrast_enabled) {
      document.body.classList.add('high-contrast');
    } else {
      document.body.classList.remove('high-contrast');
    }

    // Apply text-scale attribute to root HTML
    document.documentElement.setAttribute('data-text-scale', text_scale || 'medium');
  }, [preferencesQuery.data]);

  return {
    preferences: preferencesQuery.data,
    isLoading: preferencesQuery.isLoading,
    isError: preferencesQuery.isError,
    error: preferencesQuery.error,
    updateMutation,
    refetch: preferencesQuery.refetch,
  };
}
