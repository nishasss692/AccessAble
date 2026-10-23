import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Radio, Sliders, Cpu, History } from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/events', label: 'Alert Feed', icon: Radio },
  { to: '/preferences', label: 'Preferences', icon: Sliders },
  { to: '/integration', label: 'Ring Device', icon: Cpu },
];

export function Sidebar() {
  return (
    <aside
      aria-label="Primary Navigation"
      className="hidden md:flex flex-col w-64 border-r border-slate-800 bg-slate-950/40 p-4 shrink-0"
    >
      <div className="space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold tracking-wide transition-all ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_15px_rgba(6,182,212,0.15)] font-bold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                } focus:outline-none focus:ring-2 focus:ring-cyan-400`
              }
            >
              <Icon className="w-5 h-5 shrink-0" aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </div>

      <div className="mt-auto pt-6 border-t border-slate-800/80">
        <div className="p-3.5 bg-slate-900/40 border border-slate-800 rounded-xl">
          <p className="text-xs font-semibold text-slate-300">Accessibility Active</p>
          <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">
            High contrast & sensory notification hooks active for deaf & visually impaired safety.
          </p>
        </div>
      </div>
    </aside>
  );
}
