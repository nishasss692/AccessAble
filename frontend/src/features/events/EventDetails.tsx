import React from 'react';
import { EventItem } from '../../types/event';
import { formatDate } from '../../utils/format-date';
import { formatEventType, getSourceBadgeInfo } from '../../utils/event-labels';
import { AcknowledgementItem } from '../../types/acknowledgement';
import { AcknowledgementButton } from '../acknowledgements/AcknowledgementButton';
import { AcknowledgementHistory } from '../acknowledgements/AcknowledgementHistory';

interface EventDetailsProps {
  event: EventItem;
  history: AcknowledgementItem[];
  onActionSuccess?: () => void;
}

export function EventDetails({ event, history, onActionSuccess }: EventDetailsProps) {
  const sourceInfo = getSourceBadgeInfo(event.source);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Event Telemetry Details</h2>
        <span className={`px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wider border ${sourceInfo.bgClass}`}>
          {sourceInfo.label}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
          <p className="text-xs text-slate-400 uppercase font-semibold">Event Type</p>
          <p className="text-base font-bold text-cyan-400">{formatEventType(event.event_type)}</p>
          <p className="text-xs text-slate-400 font-mono">Raw: {event.event_type}</p>
        </div>

        <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
          <p className="text-xs text-slate-400 uppercase font-semibold">Device & ID</p>
          <p className="text-base font-bold text-slate-100 font-mono">{event.device_id || 'Unknown Device'}</p>
          <p className="text-xs text-slate-400 font-mono">DB Event ID #{event.id}</p>
        </div>
      </div>

      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Timestamps</h3>
        <div className="flex flex-col sm:flex-row gap-4 text-xs font-mono text-slate-300">
          <div>
            <span className="text-slate-500 block">Occurred At (UTC):</span>
            <span>{formatDate(event.occurred_at)}</span>
          </div>
          <div>
            <span className="text-slate-500 block">Ingested At (UTC):</span>
            <span>{formatDate(event.received_at)}</span>
          </div>
        </div>
      </div>

      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Raw Supplemental Metadata</h3>
        <pre className="p-3 bg-slate-950 rounded-lg text-xs font-mono text-cyan-300 border border-slate-800 overflow-x-auto">
          {JSON.stringify(event.metadata, null, 2)}
        </pre>
      </div>

      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Resident Action</h3>
        <AcknowledgementButton
          eventId={event.id}
          currentAction={history[0]?.action}
          onSuccess={onActionSuccess}
        />
        <AcknowledgementHistory items={history} />
      </div>
    </div>
  );
}
