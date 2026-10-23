import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getEvents, createEvent } from '../services/events-api';
import { EventCreate, EventFilterParams, EventListResponse } from '../types/event';
import { audioAlert, triggerVisualFlash } from '../utils/accessibility';
import { usePreferences } from './usePreferences';
import { useRef, useEffect } from 'react';

export function useEvents(filters: EventFilterParams = {}, pollInterval = 4000) {
  const queryClient = useQueryClient();
  const { preferences } = usePreferences();
  const previousLatestIdRef = useRef<number | null>(null);

  const eventsQuery = useQuery<EventListResponse>({
    queryKey: ['events', filters],
    queryFn: () => getEvents(filters),
    refetchInterval: pollInterval,
  });

  // Watch for newly ingested alerts and trigger sensory alerts if enabled
  useEffect(() => {
    if (!eventsQuery.data || eventsQuery.data.items.length === 0) return;
    const latestEvent = eventsQuery.data.items[0];

    if (previousLatestIdRef.current !== null && latestEvent.id > previousLatestIdRef.current) {
      if (preferences?.visual_alerts_enabled) {
        triggerVisualFlash();
      }
      if (preferences?.audio_alerts_enabled) {
        const type = latestEvent.event_type.includes('doorbell') ? 'doorbell' : 'motion';
        audioAlert.playChime(type);
      }
    }
    previousLatestIdRef.current = latestEvent.id;
  }, [eventsQuery.data, preferences]);

  const simulateEventMutation = useMutation({
    mutationFn: (newEvent: EventCreate) => createEvent(newEvent),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
      if (preferences?.visual_alerts_enabled) {
        triggerVisualFlash();
      }
      if (preferences?.audio_alerts_enabled) {
        const type = data.event.event_type.includes('doorbell') ? 'doorbell' : 'motion';
        audioAlert.playChime(type);
      }
    },
  });

  return {
    events: eventsQuery.data?.items ?? [],
    total: eventsQuery.data?.total ?? 0,
    isLoading: eventsQuery.isLoading,
    isError: eventsQuery.isError,
    error: eventsQuery.error,
    refetch: eventsQuery.refetch,
    simulateEventMutation,
  };
}
