import React, { useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { AcknowledgementButton } from '../acknowledgements/AcknowledgementButton';
import { AcknowledgementStatus } from '../acknowledgements/AcknowledgementStatus';
import { AcknowledgementHistory } from '../acknowledgements/AcknowledgementHistory';
import { EventItem } from '../../types/event';
import { getSourceBadgeInfo, formatEventType, isDemoEvent } from '../../utils/event-labels';
import { formatDate, formatRelativeTime } from '../../utils/format-date';
import { useQuery } from '@tanstack/react-query';
import { getAcknowledgements } from '../../services/acknowledgements-api';
import { Bell, Eye, Info, ShieldAlert } from 'lucide-react';

interface EventCardProps {
  event: EventItem;
  onSelect?: (event: EventItem) => void;
}

export function EventCard({ event }: EventCardProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const sourceInfo = getSourceBadgeInfo(event.source);
  const isDemo = isDemoEvent(event.source);

  // Fetch acknowledgement state for this card
  const acksQuery = useQuery({
    queryKey: ['acknowledgements', event.id],
    queryFn: () => getAcknowledgements({ event_id: event.id, limit: 10 }),
  });

  const latestAck = acksQuery.data?.items?.[0];

  return (
    <>
      <Card
        className={`transition-all duration-200 ${
          isDemo ? 'border-l-4 border-l-amber-500' : 'border-l-4 border-l-cyan-500'
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {/* Distinct Demo vs Live Ring badge */}
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider border ${sourceInfo.bgClass}`}
              >
                {sourceInfo.label}
              </span>

              <AcknowledgementStatus action={latestAck?.action} />

              <span className="text-xs text-slate-400 font-mono">
                ID #{event.id}
              </span>
            </div>

            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Bell className="w-4 h-4 text-cyan-400" aria-hidden="true" />
                <span>{formatEventType(event.event_type)}</span>
              </h3>
              <p className="text-xs text-slate-300 mt-0.5">
                Device: <span className="font-mono text-cyan-300">{event.device_id || 'Unknown Sensor'}</span>
                {event.external_event_id && (
                  <span className="ml-2 text-slate-400">
                    (External: {event.external_event_id})
                  </span>
                )}
              </p>
            </div>

            {isDemo && (
              <p className="text-[11px] text-amber-300/80 bg-amber-950/20 px-2 py-1 rounded border border-amber-500/20 max-w-lg">
                ⚠️ Simulated Demo: Generated for accessibility alert validation.
              </p>
            )}
          </div>

          <div className="flex flex-col sm:items-end justify-between gap-3 shrink-0">
            <div className="text-left sm:text-right">
              <time
                dateTime={event.occurred_at}
                className="text-xs font-semibold text-slate-200 block"
              >
                {formatRelativeTime(event.occurred_at)}
              </time>
              <span className="text-[11px] text-slate-400 font-mono">
                {formatDate(event.occurred_at)}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDetailsOpen(true)}
                aria-label={`View details and history for event #${event.id}`}
              >
                <Info className="w-3.5 h-3.5" />
                <span>Details & Audit</span>
              </Button>

              <AcknowledgementButton
                eventId={event.id}
                currentAction={latestAck?.action}
                onSuccess={() => acksQuery.refetch()}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Details & Audit Dialog */}
      <Dialog
        isOpen={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        title={`Event #${event.id} Telemetry & Audit`}
      >
        <div className="space-y-5 text-sm">
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400 font-semibold uppercase">Source Type:</span>
              <span className={`font-bold px-2 py-0.5 rounded text-[10px] ${sourceInfo.bgClass}`}>
                {sourceInfo.label}
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400 font-semibold uppercase">Event Type:</span>
              <span className="font-mono text-cyan-300 font-bold">{event.event_type}</span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400 font-semibold uppercase">Occurred At:</span>
              <span className="font-mono text-slate-200">{formatDate(event.occurred_at)}</span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400 font-semibold uppercase">Received At:</span>
              <span className="font-mono text-slate-200">{formatDate(event.received_at)}</span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400 font-semibold uppercase">Device ID:</span>
              <span className="font-mono text-slate-200">{event.device_id || 'N/A'}</span>
            </div>
          </div>

          {/* Supplemental Metadata JSON */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
              Supplemental Telemetry Payload
            </h4>
            <pre className="p-3 bg-slate-950 rounded-lg text-xs font-mono text-cyan-300 border border-slate-800 overflow-x-auto">
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          </div>

          {/* Acknowledgement Action Trigger */}
          <div className="pt-2 border-t border-slate-800">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
              Resident Response Action
            </h4>
            <AcknowledgementButton
              eventId={event.id}
              currentAction={latestAck?.action}
              onSuccess={() => acksQuery.refetch()}
            />
          </div>

          {/* Audit History Log */}
          <AcknowledgementHistory
            items={acksQuery.data?.items ?? []}
            isLoading={acksQuery.isLoading}
          />
        </div>
      </Dialog>
    </>
  );
}
