import React from 'react';
import { Select } from '../../components/ui/Select';
import { Button } from '../../components/ui/Button';
import { EventFilterParams } from '../../types/event';
import { Filter, RotateCcw } from 'lucide-react';

interface EventFiltersProps {
  filters: EventFilterParams;
  onChange: (newFilters: EventFilterParams) => void;
  onReset: () => void;
}

export function EventFilters({ filters, onChange, onReset }: EventFiltersProps) {
  const sourceOptions = [
    { value: '', label: 'All Sources (Demo & Ring)' },
    { value: 'ring', label: 'Ring Hardware Devices' },
    { value: 'demo', label: 'Simulated Demo Events' },
  ];

  const typeOptions = [
    { value: '', label: 'All Event Types' },
    { value: 'motion', label: 'Motion Detection' },
    { value: 'doorbell_ring', label: 'Doorbell Ring / Chime' },
    { value: 'doorbell_press', label: 'Doorbell Button Press' },
  ];

  return (
    <div
      role="search"
      aria-label="Filter events"
      className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl flex flex-wrap items-end gap-4"
    >
      <div className="flex-1 min-w-[200px]">
        <Select
          label="Source Filter"
          options={sourceOptions}
          value={filters.source || ''}
          onChange={(e) => onChange({ ...filters, source: e.target.value || undefined, offset: 0 })}
        />
      </div>

      <div className="flex-1 min-w-[200px]">
        <Select
          label="Event Type"
          options={typeOptions}
          value={filters.event_type || ''}
          onChange={(e) => onChange({ ...filters, event_type: e.target.value || undefined, offset: 0 })}
        />
      </div>

      <Button
        variant="ghost"
        size="md"
        onClick={onReset}
        aria-label="Reset all filters"
        className="h-10 border border-slate-700/60"
      >
        <RotateCcw className="w-4 h-4 text-slate-400" />
        <span>Reset</span>
      </Button>
    </div>
  );
}
