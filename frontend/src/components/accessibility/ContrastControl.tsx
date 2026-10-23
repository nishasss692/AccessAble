import React from 'react';
import { Eye } from 'lucide-react';
import { usePreferences } from '../../hooks/usePreferences';

export function ContrastControl() {
  const { preferences, updateMutation } = usePreferences();
  const isHighContrast = preferences?.high_contrast_enabled ?? false;

  const handleToggle = () => {
    if (!preferences) return;
    updateMutation.mutate({
      ...preferences,
      high_contrast_enabled: !isHighContrast,
    });
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={updateMutation.isPending}
      aria-label={`Toggle high contrast mode. Currently ${isHighContrast ? 'enabled' : 'disabled'}`}
      aria-pressed={isHighContrast}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all duration-200 border focus:outline-none focus:ring-2 focus:ring-cyan-400 ${
        isHighContrast
          ? 'bg-yellow-400 text-black border-yellow-300 font-bold shadow-[0_0_15px_rgba(250,204,21,0.5)]'
          : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:border-slate-500 hover:text-white'
      }`}
    >
      <Eye className="w-4 h-4" aria-hidden="true" />
      <span>{isHighContrast ? 'Contrast: High' : 'Contrast: Normal'}</span>
    </button>
  );
}
