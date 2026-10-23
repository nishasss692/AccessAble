import React from 'react';
import { EventItem } from '../../types/event';
import { EventCard } from './EventCard';
import { LoadingState, ErrorState } from '../../components/ui/LoadingState';
import { Radio } from 'lucide-react';

interface EventListProps {
  events: EventItem[];
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  onRetry?: () => void;
  onSelectEvent?: (event: EventItem) => void;
}

export function EventList({
  events,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  onSelectEvent,
}: EventListProps) {
  if (isLoading) {
    return <LoadingState message="Polling live telemetry from AccessAble backend..." />;
  }

  if (isError) {
    return (
      <ErrorState
        title="Failed to Load Event History"
        message={errorMessage || 'Could not connect to the events endpoint. Verify FastAPI is online.'}
        onRetry={onRetry}
      />
    );
  }

  if (events.length === 0) {
    return (
      <div
        role="status"
        className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/20"
      >
        <Radio className="w-10 h-10 text-slate-600 mb-3" aria-hidden="true" />
        <h3 className="text-base font-semibold text-slate-300">No events found</h3>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          No telemetry events match your criteria. You can ingest a demo event from the dashboard to test alerts.
        </p>
      </div>
    );
  }

  return (
    <div
      role="feed"
      aria-busy={isLoading}
      aria-label="Sensory alert events"
      className="space-y-3"
    >
      {events.map((event) => (
        <EventCard key={event.id} event={event} onSelect={onSelectEvent} />
      ))}
    </div>
  );
}
