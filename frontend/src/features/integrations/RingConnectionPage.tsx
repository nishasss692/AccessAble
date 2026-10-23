import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRingStatus } from '../../services/ring-api';
import { RingConnectionStatus } from './RingConnectionStatus';
import { LoadingState, ErrorState } from '../../components/ui/LoadingState';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Cpu, RefreshCw, Sparkles, CheckCircle2 } from 'lucide-react';
import { useEvents } from '../../hooks/useEvents';

export function RingConnectionPage() {
  const { data: ringStatus, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['ring-status'],
    queryFn: getRingStatus,
    refetchInterval: 10000,
  });

  const { simulateEventMutation } = useEvents();

  const handleSimulateHardwareIngest = () => {
    simulateEventMutation.mutate({
      source: 'demo',
      external_event_id: `ring-sim-${Date.now()}`,
      event_type: 'doorbell_ring',
      occurred_at: new Date().toISOString(),
      device_id: 'front-porch-doorbell-pro',
      metadata: {
        signal_strength: 'good',
        battery: 94,
        simulation: true,
      },
    });
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-wide flex items-center gap-2.5">
            <Cpu className="w-6 h-6 text-cyan-400" />
            <span>Ring Smart Device Bridge</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Integration telemetry and hardware communication status with the Ring ecosystem.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Check Status</span>
        </Button>
      </div>

      {isLoading ? (
        <LoadingState message="Querying Ring integration bridge..." />
      ) : isError || !ringStatus ? (
        <ErrorState
          title="Integration Bridge Query Failed"
          message={(error as Error)?.message || 'Failed to communicate with /api/v1/integrations/ring/status'}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="space-y-6">
          <RingConnectionStatus ringStatus={ringStatus} />

          {/* Demonstration Mode Disclaimer & Test Section */}
          <Card className="space-y-4 border-amber-500/30 bg-amber-950/10">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-amber-300 uppercase tracking-wider">
                  Development Simulation Mode
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  As documented in the Ring integration specification, when live Ring credentials are not configured, the bridge reports an `unknown` state with full support for demo simulation. Simulated events will be processed by the real database and trigger all visual and audio accessibility alerts.
                </p>
              </div>
            </div>

            <div className="pt-2 flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                disabled={simulateEventMutation.isPending}
                onClick={handleSimulateHardwareIngest}
                className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
              >
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span>Simulate Ring Doorbell Ingestion</span>
              </Button>

              {simulateEventMutation.isSuccess && (
                <span className="text-xs text-emerald-400 flex items-center gap-1 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Simulated event ingested successfully!</span>
                </span>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
