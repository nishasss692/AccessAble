import React from 'react';
import { EventItem } from '../../types/event';
import { EventCard } from '../events/EventCard';
import { LoadingState } from '../../components/ui/LoadingState';
import { NavLink } from 'react-router-dom';
import { ArrowRight, Bell } from 'lucide-react';

interface RecentEventsProps {
  events: EventItem[];
  isLoading: boolean;
}

export function RecentEvents({ events, isLoading }: RecentEventsProps) {
  if (isLoading) {
    return <LoadingState message="Streaming active events..." />;
  }

  const recent = events.slice(0, 5);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Bell className="w-5 h-5 text-cyan-400" />
          <span>Recent Sensory Events</span>
        </h2>
        <NavLink
          to="/events"
          className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-cyan-400 rounded px-1"
        >
          <span>View All ({events.length})</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </NavLink>
      </div>

      {recent.length === 0 ? (
        <div className="p-8 border border-dashed border-slate-800 rounded-xl text-center text-slate-500 text-xs">
          No events recorded yet. Ingest a simulated alert above to test accessibility alerts!
        </div>
      ) : (
        <div className="space-y-3">
          {recent.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
