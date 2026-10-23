import React from 'react';

interface FocusIndicatorProps {
  children: React.ReactNode;
  className?: string;
}

export function FocusIndicator({ children, className = '' }: FocusIndicatorProps) {
  return (
    <div
      className={`focus-within:ring-2 focus-within:ring-cyan-400 focus-within:ring-offset-2 focus-within:ring-offset-slate-950 rounded-lg transition-shadow ${className}`}
    >
      {children}
    </div>
  );
}
