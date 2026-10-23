import React from 'react';
import { useEvents } from '../../hooks/useEvents';
import { usePreferences } from '../../hooks/usePreferences';
import { useQuery } from '@tanstack/react-query';
import { getRingStatus } from '../../services/ring-api';
import { EventSummary } from './EventSummary';
import { ConnectionStatus } from './ConnectionStatus';
import { RecentEvents } from './RecentEvents';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Sparkles, Radio, BellRing, Eye, Volume2 } from 'lucide-react';

export function DashboardPage() {
  const { events, total, isLoading, simulateEventMutation } = useEvents({ limit: 20 });
  const { preferences } = usePreferences();

  const { data: ringStatus, isLoading: ringLoading } = useQuery({
    queryKey: ['ring-status'],
    queryFn: getRingStatus,
    refetchInterval: 10000,
  });

  const handleSimulateAlert = (type: 'doorbell_ring' | 'motion') => {
    simulateEventMutation.mutate({
      source: 'demo',
      external_event_id: `demo-${Date.now()}`,
      event_type: type,
      occurred_at: new Date().toISOString(),
      device_id: type === 'doorbell_ring' ? 'front-doorbell' : 'driveway-sensor',
      metadata: {
        battery: 88,
        motion_score: 95,
        test_simulation: true,
      },
    });
  };

  return (
    <div className="space-y-8">
      {/* Page Title & Status */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">
            Telemetry Dashboard
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Accessible multi-sensory smart doorbell & security hub for deaf and low-vision residents.
          </p>
        </div>

        {/* Quick Simulation Bar */}
        <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 p-1.5 rounded-xl">
          <span className="text-xs font-bold text-amber-300 uppercase px-2 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Simulate:</span>
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={simulateEventMutation.isPending}
            onClick={() => handleSimulateAlert('doorbell_ring')}
            aria-label="Simulate Doorbell Ring Alert"
          >
            <BellRing className="w-3.5 h-3.5 text-cyan-400" />
            <span>Doorbell</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={simulateEventMutation.isPending}
            onClick={() => handleSimulateAlert('motion')}
            aria-label="Simulate Motion Detection Alert"
          >
            <Radio className="w-3.5 h-3.5 text-amber-400" />
            <span>Motion</span>
          </Button>
        </div>
      </div>

      {/* Sensory Alerts Status Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="flex items-center gap-3 py-3 px-4">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Eye className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs text-slate-400 block font-semibold">Visual Alerts</span>
            <span className="text-sm font-bold text-slate-200">
              {preferences?.visual_alerts_enabled ? 'Active (Screen Pulse)' : 'Disabled'}
            </span>
          </div>
        </Card>

        <Card className="flex items-center gap-3 py-3 px-4">
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
            <Volume2 className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs text-slate-400 block font-semibold">Audio Chimes</span>
            <span className="text-sm font-bold text-slate-200">
              {preferences?.audio_alerts_enabled ? 'Active (Dual Chime)' : 'Muted'}
            </span>
          </div>
        </Card>

        <ConnectionStatus ringStatus={ringStatus} isLoading={ringLoading} />
      </div>

      {/* Telemetry Summary Stats */}
      <EventSummary events={events} total={total} />

      {/* Recent Alerts Feed */}
      <RecentEvents events={events} isLoading={isLoading} />
    </div>
  );
}
