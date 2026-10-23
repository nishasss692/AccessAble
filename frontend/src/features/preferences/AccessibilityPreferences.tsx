import React from 'react';
import { Card } from '../../components/ui/Card';
import { Toggle } from '../../components/ui/Toggle';
import { Select } from '../../components/ui/Select';
import { PreferencesResponse, TextScaleType } from '../../types/preferences';
import { Eye, Type, SunMoon } from 'lucide-react';

interface AccessibilityPreferencesProps {
  preferences: PreferencesResponse;
  onChange: (updated: PreferencesResponse) => void;
  disabled?: boolean;
}

export function AccessibilityPreferences({
  preferences,
  onChange,
  disabled = false,
}: AccessibilityPreferencesProps) {
  const textScaleOptions = [
    { value: 'small', label: 'Small (Compact UI)' },
    { value: 'medium', label: 'Medium (Standard 16px)' },
    { value: 'large', label: 'Large (High Legibility 19px)' },
  ];

  return (
    <Card className="space-y-6">
      <div className="flex items-center gap-3 pb-3 border-b border-slate-800">
        <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
          <Eye className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Visual & Typography Accessibility</h2>
          <p className="text-xs text-slate-400">
            Tailor high-contrast themes and text scaling for maximum readability.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <Toggle
          label="High Contrast Color Mode"
          description="Enforces pure black background (#000000), vivid high-contrast text and luminous yellow borders (>2px)."
          checked={preferences.high_contrast_enabled}
          disabled={disabled}
          onChange={(checked) =>
            onChange({
              ...preferences,
              high_contrast_enabled: checked,
            })
          }
        />

        <div className="pt-2 border-t border-slate-800/60">
          <Select
            label="Root Typography Scaling (text_scale)"
            options={textScaleOptions}
            value={preferences.text_scale}
            disabled={disabled}
            onChange={(e) =>
              onChange({
                ...preferences,
                text_scale: e.target.value as TextScaleType,
              })
            }
          />
          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
            Scales typography across all feeds, status indicators, and buttons via data-text-scale root mapping.
          </p>
        </div>
      </div>
    </Card>
  );
}
