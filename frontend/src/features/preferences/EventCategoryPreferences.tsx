import React from 'react';
import { Card } from '../../components/ui/Card';
import { BellRing, ShieldAlert, Cpu } from 'lucide-react';

export function EventCategoryPreferences() {
  return (
    <Card className="space-y-4">
      <div className="flex items-center gap-3 pb-3 border-b border-slate-800">
        <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
          <BellRing className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Event Category Telemetry Rules</h2>
          <p className="text-xs text-slate-400">
            Hardware priority handling across doorbell and motion channels.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-xl space-y-1">
          <span className="font-bold text-cyan-400 uppercase flex items-center gap-1.5">
            <BellRing className="w-4 h-4" />
            <span>Doorbell Rings</span>
          </span>
          <p className="text-slate-400">
            Classified as Critical / High Priority. Always triggers highest visual beacon and primary chime.
          </p>
        </div>

        <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-xl space-y-1">
          <span className="font-bold text-purple-400 uppercase flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4" />
            <span>Motion Sensors</span>
          </span>
          <p className="text-slate-400">
            Classified as Informational. Triggers peripheral indicator and single brief acoustic chirp.
          </p>
        </div>
      </div>
    </Card>
  );
}
