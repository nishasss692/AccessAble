import React, { useState } from 'react';
import { useEvents } from '../../hooks/useEvents';
import { EventFilters } from './EventFilters';
import { EventList } from './EventList';
import { EventFilterParams } from '../../types/event';
import { Radio, RefreshCw } from 'lucide-react';
import { Button } from '../../components/ui/Button';

export function EventsPage() {
  const [filters, setFilters] = useState<EventFilterParams>({ limit: 50 });
  const { events, total, isLoading, isError, error, refetch } = useEvents(filters);

  const handleResetFilters = () => {
    setFilters({ limit: 50 });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-wide flex items-center gap-2.5">
            <Radio className="w-6 h-6 text-cyan-400" aria-hidden="true" />
            <span>Sensory Alert History</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time telemetry and audit stream. Showing {events.length} of {total} events.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
          aria-label="Refresh events feed"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Telemetry</span>
        </Button>
      </div>

      <EventFilters
        filters={filters}
        onChange={setFilters}
        onReset={handleResetFilters}
      />

      <EventList
        events={events}
        isLoading={isLoading}
        isError={isError}
        errorMessage={(error as Error)?.message}
        onRetry={() => refetch()}
      />
    </div>
  );
}
