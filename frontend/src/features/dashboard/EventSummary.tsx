import React from 'react';
import { Card } from '../../components/ui/Card';
import { EventItem } from '../../types/event';
import { Bell, Eye, CheckCircle2, ShieldAlert } from 'lucide-react';
import { isDemoEvent } from '../../utils/event-labels';

interface EventSummaryProps {
  events: EventItem[];
  total: number;
}

export function EventSummary({ events, total }: EventSummaryProps) {
  const demoCount = events.filter((e) => isDemoEvent(e.source)).length;
  const liveCount = events.filter((e) => !isDemoEvent(e.source)).length;
  const doorbellCount = events.filter((e) => e.event_type.includes('doorbell')).length;
  const motionCount = events.filter((e) => e.event_type.includes('motion')).length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
          <Bell className="w-6 h-6" />
        </div>
        <div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Total Ingested
          </span>
          <span className="text-2xl font-black text-white">{total}</span>
        </div>
      </Card>

      <Card className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Live Hardware
          </span>
          <span className="text-2xl font-black text-emerald-400">{liveCount}</span>
        </div>
      </Card>

      <Card className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Simulated Demo
          </span>
          <span className="text-2xl font-black text-amber-400">{demoCount}</span>
        </div>
      </Card>

      <Card className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
          <Eye className="w-6 h-6" />
        </div>
        <div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Doorbell / Motion
          </span>
          <span className="text-2xl font-black text-white">
            {doorbellCount} <span className="text-sm font-normal text-slate-400">/ {motionCount}</span>
          </span>
        </div>
      </Card>
    </div>
  );
}
