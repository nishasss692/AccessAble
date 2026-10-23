import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { useAcknowledgement } from '../../hooks/useAcknowledgement';
import { ActionType } from '../../types/acknowledgement';

interface AcknowledgementButtonProps {
  eventId: number;
  currentAction?: ActionType | null;
  onSuccess?: () => void;
}

export function AcknowledgementButton({
  eventId,
  currentAction,
  onSuccess,
}: AcknowledgementButtonProps) {
  const { acknowledge, isPending, conflictError, resetConflict } = useAcknowledgement();

  const handleAction = (action: ActionType) => {
    acknowledge(
      {
        event_id: eventId,
        action,
        note: action === 'acknowledged' ? 'Acknowledged from event view' : 'Dismissed from event view',
      },
      {
        onSuccess: () => {
          if (onSuccess) onSuccess();
        },
      }
    );
  };

  const isAcknowledged = currentAction === 'acknowledged';
  const isDismissed = currentAction === 'dismissed';

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant={isAcknowledged ? 'secondary' : 'primary'}
          disabled={isPending || isAcknowledged}
          onClick={() => handleAction('acknowledged')}
          aria-label={`Acknowledge event #${eventId}`}
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{isAcknowledged ? 'Acknowledged' : 'Acknowledge'}</span>
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={isPending || isDismissed}
          onClick={() => handleAction('dismissed')}
          aria-label={`Dismiss event #${eventId}`}
        >
          <XCircle className="w-4 h-4 text-slate-400" />
          <span>{isDismissed ? 'Dismissed' : 'Dismiss'}</span>
        </Button>
      </div>

      {conflictError && (
        <div
          role="alert"
          className="flex items-center justify-between text-xs text-amber-300 bg-amber-950/40 border border-amber-500/30 px-3 py-1.5 rounded-lg"
        >
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>{conflictError}</span>
          </div>
          <button
            type="button"
            onClick={resetConflict}
            className="text-amber-400 hover:text-white font-bold ml-2"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
