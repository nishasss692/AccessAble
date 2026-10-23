import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createAcknowledgement } from '../services/acknowledgements-api';
import { AcknowledgementCreate, AcknowledgementItem } from '../types/acknowledgement';
import { useState } from 'react';

export function useAcknowledgement() {
  const queryClient = useQueryClient();
  const [conflictError, setConflictError] = useState<string | null>(null);

  const mutation = useMutation<AcknowledgementItem, Error, AcknowledgementCreate>({
    mutationFn: (data: AcknowledgementCreate) => createAcknowledgement(data),
    onSuccess: (data) => {
      setConflictError(null);
      // Invalidate relevant event and acknowledgement queries
      queryClient.invalidateQueries({ queryKey: ['acknowledgements'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['event', data.event_id] });
    },
    onError: (err: any) => {
      if (err?.status === 409 || err?.message?.includes('already')) {
        setConflictError(err.message || 'Event has already been transitioned to this state.');
      }
    },
  });

  return {
    acknowledge: mutation.mutate,
    acknowledgeAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    conflictError,
    resetConflict: () => setConflictError(null),
  };
}
