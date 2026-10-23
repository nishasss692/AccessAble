import React from 'react';
import { EventItem } from '../../types/event';
import { formatDate } from '../../utils/format-date';
import { formatEventType, getSourceBadgeInfo } from '../../utils/event-labels';

interface EventTimelineProps {
  events: EventItem[];
}

export function EventTimeline({ events }: EventTimelineProps) {
  if (events.length === 0) {
    return <p className="text-xs text-slate-500 py-4">No events in timeline.</p>;
  }

  return (
    <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
      {events.map((event) => {
        const sourceInfo = getSourceBadgeInfo(event.source);
        return (
          <div key={event.id} className="relative group">
            <span
              className={`absolute -left-6 top-1.5 w-4 h-4 rounded-full border-2 border-slate-950 ${
                sourceInfo.isLive ? 'bg-cyan-400' : 'bg-amber-400'
              }`}
            />
            <div className="p-3 bg-slate-900/50 border border-slate-800/80 rounded-xl hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-bold text-white">{formatEventType(event.event_type)}</span>
                <time className="text-slate-400 font-mono text-[11px]">{formatDate(event.occurred_at)}</time>
              </div>
              <p className="text-xs text-slate-400">
                Source: <span className="font-semibold text-slate-300">{sourceInfo.label}</span> • Device: {event.device_id || 'N/A'}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
