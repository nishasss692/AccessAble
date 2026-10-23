import React from 'react';
import { Loader2, AlertCircle } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = 'Loading sensory telemetry...' }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center p-12 text-center text-slate-400"
    >
      <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mb-3" aria-hidden="true" />
      <p className="text-sm font-medium tracking-wide">{message}</p>
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = 'Telemetry Connection Interrupted',
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center p-8 bg-rose-950/20 border border-rose-500/30 rounded-xl text-center text-rose-200"
    >
      <AlertCircle className="w-8 h-8 text-rose-400 mb-2" aria-hidden="true" />
      <h3 className="font-bold text-base text-rose-100 mb-1">{title}</h3>
      <p className="text-sm text-rose-300/90 max-w-md mb-4">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs tracking-wider uppercase rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-rose-400"
        >
          Retry Connection
        </button>
      )}
    </div>
  );
}
