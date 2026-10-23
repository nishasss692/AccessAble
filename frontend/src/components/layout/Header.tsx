import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, Bell, Sliders, ShieldCheck } from 'lucide-react';
import { ContrastControl } from '../accessibility/ContrastControl';
import { TextSizeControl } from '../accessibility/TextSizeControl';
import { useQuery } from '@tanstack/react-query';
import { getRingStatus } from '../../services/ring-api';
import { getRingStatusBadge } from '../../utils/status-labels';

export function Header() {
  const { data: ringStatus } = useQuery({
    queryKey: ['ring-status'],
    queryFn: getRingStatus,
    refetchInterval: 10000,
  });

  const badge = getRingStatusBadge(ringStatus?.status ?? 'unknown');

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <NavLink
            to="/"
            className="flex items-center gap-3 group focus:outline-none focus:ring-2 focus:ring-cyan-400 rounded-lg p-1"
          >
            <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/40 flex items-center justify-center text-cyan-400 group-hover:border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.2)]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <span className="text-lg font-black tracking-wider text-white flex items-center gap-1.5">
                ACCESS<span className="text-cyan-400">ABLE</span>
              </span>
              <span className="text-[10px] uppercase font-mono tracking-widest text-slate-400 block -mt-1">
                Sensory Telemetry
              </span>
            </div>
          </NavLink>
        </div>

        {/* Ring Integration Status Pill */}
        <div className="hidden md:flex items-center">
          <NavLink
            to="/integration"
            className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold border transition-all ${badge.bgClass} hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-cyan-400`}
            title={badge.description}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                ringStatus?.is_connected ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-400'
              }`}
              aria-hidden="true"
            />
            <span>Ring: {badge.label}</span>
          </NavLink>
        </div>

        {/* Accessibility Quick Toggles */}
        <div className="flex items-center gap-3">
          <TextSizeControl />
          <ContrastControl />
        </div>
      </div>
    </header>
  );
}
