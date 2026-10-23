import React from 'react';
import { Card } from '../../components/ui/Card';
import { RingStatusResponse } from '../../types/preferences';
import { getRingStatusBadge } from '../../utils/status-labels';
import { formatDate } from '../../utils/format-date';
import { Cpu, ShieldCheck, ShieldAlert, AlertTriangle } from 'lucide-react';

interface RingConnectionStatusProps {
  ringStatus: RingStatusResponse;
}

export function RingConnectionStatus({ ringStatus }: RingConnectionStatusProps) {
  const badge = getRingStatusBadge(ringStatus.status);

  return (
    <Card className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Ring Integration Adapter</h2>
            <p className="text-xs text-slate-400 font-mono">Source ID: {ringStatus.source}</p>
          </div>
        </div>

        <span className={`px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${badge.bgClass}`}>
          {badge.label}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
          <span className="text-slate-500 uppercase block font-semibold mb-1">Health Verified</span>
          <span className="text-slate-200">
            {ringStatus.last_checked_at ? formatDate(ringStatus.last_checked_at) : 'Not Checked Yet'}
          </span>
        </div>

        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
          <span className="text-slate-500 uppercase block font-semibold mb-1">Last Event Sync</span>
          <span className="text-slate-200">
            {ringStatus.last_successful_sync_at ? formatDate(ringStatus.last_successful_sync_at) : 'Never synced live'}
          </span>
        </div>
      </div>

      <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800 space-y-2 text-xs">
        <h4 className="font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>Operational Details</span>
        </h4>
        <p className="text-slate-300 leading-relaxed">
          {ringStatus.details?.note || badge.description}
        </p>
        {ringStatus.details?.mode && (
          <p className="text-slate-400 font-mono">
            Configured Mode: <span className="text-cyan-400">{ringStatus.details.mode}</span>
          </p>
        )}
      </div>

      {ringStatus.error_message && (
        <div className="p-4 bg-rose-950/30 border border-rose-500/40 rounded-xl text-xs text-rose-300">
          <span className="font-bold block mb-1">Bridge Error Message:</span>
          {ringStatus.error_message}
        </div>
      )}
    </Card>
  );
}
