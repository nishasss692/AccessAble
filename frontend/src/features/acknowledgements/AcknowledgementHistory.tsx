


import React from 'react';
import { AcknowledgementItem } from '../../types/acknowledgement';
import { formatDate } from '../../utils/format-date';
import { CheckCircle2, XCircle } from 'lucide-react';

interface AcknowledgementHistoryProps {
  items: AcknowledgementItem[];
  isLoading?: boolean;
}

export function AcknowledgementHistory({ items, isLoading }: AcknowledgementHistoryProps) {
  if (isLoading) {
    return <div className="text-xs text-slate-400 py-2">Loading action audit log...</div>;
  }

  if (items.length === 0) {
    return (
      <div className="text-xs text-slate-400 italic py-2">
        No past acknowledgements or dismissals recorded for this event.
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
        Action Audit History ({items.length})
      </h4>
      <div className="divide-y divide-slate-800 border border-slate-800 rounded-lg bg-slate-900/40 overflow-hidden">
        {items.map((item) => (
          <div key={item.id} className="p-3 flex items-start justify-between gap-3 text-xs">
            <div className="flex items-start gap-2">
              {item.action === 'acknowledged' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
              )}
              <div>
                <p className="font-semibold text-slate-200 capitalize">
                  Action: {item.action}
                </p>
                {item.note && (
                  <p className="text-slate-400 mt-0.5">Note: "{item.note}"</p>
                )}
              </div>
            </div>
            <time className="text-[11px] text-slate-400 font-mono shrink-0">
              {formatDate(item.acknowledged_at)}
            </time>
          </div>
        ))}
      </div>
    </div>
  );
}
