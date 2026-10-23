import React from 'react';
import { Card } from '../../components/ui/Card';
import { ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';
import { RingStatusResponse } from '../../types/preferences';
import { getRingStatusBadge } from '../../utils/status-labels';
import { formatDate } from '../../utils/format-date';

interface ConnectionStatusProps {
  ringStatus?: RingStatusResponse;
  isLoading?: boolean;
}

export function ConnectionStatus({ ringStatus, isLoading }: ConnectionStatusProps) {
  const badge = getRingStatusBadge(ringStatus?.status ?? 'unknown');

  return (
    <Card className="flex flex-col justify-between" glow={ringStatus?.is_connected}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
            Integration Bridge
          </span>
          <h3 className="text-lg font-bold text-white mt-1 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <span>Ring Smart System</span>
          </h3>
        </div>

        <span className={`px-2.5 py-1 rounded-full text-xs font-bold border uppercase ${badge.bgClass}`}>
          {badge.label}
        </span>
      </div>

      <div className="mt-4 pt-4 border-t border-slate-800 text-xs space-y-1.5">
        <p className="text-slate-300 leading-relaxed">
          {ringStatus?.details?.note || badge.description}
        </p>
        {ringStatus?.last_checked_at && (
          <p className="text-[11px] text-slate-400 font-mono">
            Last Checked: {formatDate(ringStatus.last_checked_at)}
          </p>
        )}
      </div>
    </Card>
  );
}
