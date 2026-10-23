import { useQuery } from '@tanstack/react-query';
import { getEvents } from '../services/events-api';
import { getAcknowledgements } from '../services/acknowledgements-api';
import { EventItem } from '../types/event';
import { AcknowledgementItem } from '../types/acknowledgement';

export function useEventDetails(eventId: number | null) {
  const eventQuery = useQuery<EventItem | null>({
    queryKey: ['event', eventId],
    queryFn: async () => {
      if (!eventId) return null;
      const res = await getEvents({ limit: 100 });
      const found = res.items.find((e) => e.id === eventId);
      return found || null;
    },
    enabled: !!eventId,
  });

  const historyQuery = useQuery<AcknowledgementItem[]>({
    queryKey: ['acknowledgements', eventId],
    queryFn: async () => {
      if (!eventId) return [];
      const res = await getAcknowledgements({ event_id: eventId, limit: 50 });
      return res.items;
    },
    enabled: !!eventId,
  });

  return {
    event: eventQuery.data,
    history: historyQuery.data ?? [],
    isLoading: eventQuery.isLoading || historyQuery.isLoading,
    isError: eventQuery.isError || historyQuery.isError,
    error: eventQuery.error || historyQuery.error,
    refetch: () => {
      eventQuery.refetch();
      historyQuery.refetch();
    },
  };
}
