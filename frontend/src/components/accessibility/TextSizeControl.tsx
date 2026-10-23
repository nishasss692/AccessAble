import React from 'react';
import { Type } from 'lucide-react';
import { usePreferences } from '../../hooks/usePreferences';
import { TextScaleType } from '../../types/preferences';

const SCALE_OPTIONS: { value: TextScaleType; label: string }[] = [
  { value: 'small', label: 'A-' },
  { value: 'medium', label: 'A' },
  { value: 'large', label: 'A+' },
];

export function TextSizeControl() {
  const { preferences, updateMutation } = usePreferences();
  const currentScale = preferences?.text_scale || 'medium';

  const handleSelect = (scale: TextScaleType) => {
    if (!preferences || scale === currentScale) return;
    updateMutation.mutate({
      ...preferences,
      text_scale: scale,
    });
  };

  return (
    <div
      role="group"
      aria-label="Text size controls"
      className="inline-flex items-center bg-slate-900/80 border border-slate-700 rounded-lg p-0.5"
    >
      <span className="sr-only">Change text size</span>
      <div className="px-2 text-slate-400" aria-hidden="true">
        <Type className="w-3.5 h-3.5" />
      </div>
      {SCALE_OPTIONS.map((opt) => {
        const isSelected = currentScale === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => handleSelect(opt.value)}
            disabled={updateMutation.isPending}
            aria-pressed={isSelected}
            aria-label={`Set text scale to ${opt.value}`}
            className={`px-2.5 py-1 text-xs font-bold rounded-md transition-all ${
              isSelected
                ? 'bg-cyan-500 text-slate-950 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            } focus:outline-none focus:ring-2 focus:ring-cyan-400`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
