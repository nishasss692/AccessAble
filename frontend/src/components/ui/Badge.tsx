import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'cyan' | 'amber' | 'emerald' | 'rose' | 'slate';
  className?: string;
}

export function Badge({ children, variant = 'slate', className = '' }: BadgeProps) {
  const variantStyles = {
    cyan: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]',
    rose: 'bg-rose-500/15 text-rose-300 border-rose-500/30 shadow-[0_0_10px_rgba(244,63,94,0.15)]',
    slate: 'bg-slate-800 text-slate-300 border-slate-700',
  }[variant];

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border uppercase ${variantStyles} ${className}`}
    >
      {children}
    </span>
  );
}
