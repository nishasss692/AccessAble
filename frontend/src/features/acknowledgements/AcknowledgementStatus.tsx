import React from 'react';
import { Badge } from '../../components/ui/Badge';
import { ActionType } from '../../types/acknowledgement';
import { CheckCircle2, XCircle, Clock } from 'lucide-react';

interface AcknowledgementStatusProps {
  action?: ActionType | null;
  acknowledgedAt?: string | null;
}

export function AcknowledgementStatus({ action, acknowledgedAt }: AcknowledgementStatusProps) {
  if (!action) {
    return (
      <Badge variant="amber" className="text-[10px]">
        <Clock className="w-3 h-3" />
        <span>Pending Action</span>
      </Badge>
    );
  }

  if (action === 'acknowledged') {
    return (
      <Badge variant="emerald" className="text-[10px]">
        <CheckCircle2 className="w-3 h-3" />
        <span>Acknowledged</span>
      </Badge>
    );
  }

  return (
    <Badge variant="slate" className="text-[10px]">
      <XCircle className="w-3 h-3" />
      <span>Dismissed</span>
    </Badge>
  );
}
