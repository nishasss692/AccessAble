import React, { useState } from 'react';
import { usePreferences } from '../../hooks/usePreferences';
import { AccessibilityPreferences } from './AccessibilityPreferences';
import { AlertPreferences } from './AlertPreferences';
import { EventCategoryPreferences } from './EventCategoryPreferences';
import { Button } from '../../components/ui/Button';
import { LoadingState, ErrorState } from '../../components/ui/LoadingState';
import { PreferencesResponse } from '../../types/preferences';
import { Sliders, Save, CheckCircle } from 'lucide-react';
import { formatDate } from '../../utils/format-date';

export function PreferencesPage() {
  const { preferences, isLoading, isError, error, updateMutation, refetch } = usePreferences();
  const [successBanner, setSuccessBanner] = useState(false);

  const handleUpdate = (updated: PreferencesResponse) => {
    updateMutation.mutate(
      {
        visual_alerts_enabled: updated.visual_alerts_enabled,
        audio_alerts_enabled: updated.audio_alerts_enabled,
        high_contrast_enabled: updated.high_contrast_enabled,
        text_scale: updated.text_scale,
      },
      {
        onSuccess: () => {
          setSuccessBanner(true);
          setTimeout(() => setSuccessBanner(false), 3000);
        },
      }
    );
  };

  if (isLoading) {
    return <LoadingState message="Loading accessibility preferences profile..." />;
  }

  if (isError || !preferences) {
    return (
      <ErrorState
        title="Preferences Profile Unavailable"
        message={(error as Error)?.message || 'Failed to retrieve profile from backend.'}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-wide flex items-center gap-2.5">
            <Sliders className="w-6 h-6 text-cyan-400" />
            <span>Accessibility & Alert Preferences</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Persisted preferences automatically configure the sensory alert engine. Last updated: {formatDate(preferences.updated_at)}
          </p>
        </div>

        {successBanner && (
          <div
            role="status"
            className="flex items-center gap-2 text-xs font-bold text-emerald-300 bg-emerald-950/40 border border-emerald-500/40 px-3 py-2 rounded-xl animate-in fade-in"
          >
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span>Profile Synchronized</span>
          </div>
        )}
      </div>

      <div className="space-y-6">
        <AccessibilityPreferences
          preferences={preferences}
          onChange={handleUpdate}
          disabled={updateMutation.isPending}
        />

        <AlertPreferences
          preferences={preferences}
          onChange={handleUpdate}
          disabled={updateMutation.isPending}
        />

        <EventCategoryPreferences />
      </div>
    </div>
  );
}
