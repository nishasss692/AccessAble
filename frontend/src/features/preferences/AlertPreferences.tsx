import React from 'react';
import { Card } from '../../components/ui/Card';
import { Toggle } from '../../components/ui/Toggle';
import { PreferencesResponse } from '../../types/preferences';
import { Volume2, Zap } from 'lucide-react';

interface AlertPreferencesProps {
  preferences: PreferencesResponse;
  onChange: (updated: PreferencesResponse) => void;
  disabled?: boolean;
}

export function AlertPreferences({
  preferences,
  onChange,
  disabled = false,
}: AlertPreferencesProps) {
  return (
    <Card className="space-y-6">
      <div className="flex items-center gap-3 pb-3 border-b border-slate-800">
        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
          <Zap className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Sensory Notification Channels</h2>
          <p className="text-xs text-slate-400">
            Configure strobe visual flashes and synthesized audio chimes for new events.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <Toggle
          label="Visual Alert Flashes (visual_alerts_enabled)"
          description="Flashes a luminous cyan screen border overlay whenever a doorbell or security event occurs. Photosensitive-safe 300ms pulse."
          checked={preferences.visual_alerts_enabled}
          disabled={disabled}
          onChange={(checked) =>
            onChange({
              ...preferences,
              visual_alerts_enabled: checked,
            })
          }
        />

        <div className="pt-2 border-t border-slate-800/60">
          <Toggle
            label="Audio Chimes (audio_alerts_enabled)"
            description="Synthesizes distinct acoustic chimes using Web Audio API (high-low ding-dong for doorbells, rising chirps for motion)."
            checked={preferences.audio_alerts_enabled}
            disabled={disabled}
            onChange={(checked) =>
              onChange({
                ...preferences,
                audio_alerts_enabled: checked,
              })
            }
          />
        </div>
      </div>
    </Card>
  );
}
