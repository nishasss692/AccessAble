import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  glow?: boolean;
}

export function Card({ children, glow = false, className = '', ...props }: CardProps) {
  return (
    <div
      className={`relative bg-slate-900/70 backdrop-blur-md border border-slate-800 rounded-xl p-5 transition-all duration-200 ${
        glow ? 'border-cyan-500/40 shadow-[0_0_25px_rgba(6,182,212,0.15)]' : 'hover:border-slate-700'
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
