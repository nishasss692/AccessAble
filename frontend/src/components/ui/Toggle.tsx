import React from 'react';

interface ToggleProps {
  id?: string;
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function Toggle({
  id,
  label,
  description,
  checked,
  onChange,
  disabled = false,
}: ToggleProps) {
  const toggleId = id || `toggle-${label.toLowerCase().replace(/\s+/g, '-')}`;

  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="flex flex-col">
        <label htmlFor={toggleId} className="text-sm font-semibold text-slate-100 cursor-pointer">
          {label}
        </label>
        {description && (
          <span className="text-xs text-slate-400 mt-0.5 leading-relaxed">
            {description}
          </span>
        )}
      </div>
      <button
        type="button"
        id={toggleId}
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed ${
          checked ? 'bg-cyan-500' : 'bg-slate-700'
        }`}
      >
        <span
          aria-hidden="true"
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
            checked ? 'translate-x-5 bg-slate-950' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  );
}
