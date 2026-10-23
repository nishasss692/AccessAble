import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Radio, Sliders, Cpu } from 'lucide-react';

const MOBILE_NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/events', label: 'Feed', icon: Radio },
  { to: '/preferences', label: 'Settings', icon: Sliders },
  { to: '/integration', label: 'Ring', icon: Cpu },
];

export function MobileNavigation() {
  return (
    <nav
      aria-label="Mobile Bottom Navigation"
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-slate-950/90 border-t border-slate-800 backdrop-blur-md px-4 py-2"
    >
      <div className="flex items-center justify-around">
        {MOBILE_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 py-1 px-3 rounded-lg text-xs font-semibold transition-all ${
                  isActive ? 'text-cyan-400' : 'text-slate-400 hover:text-slate-200'
                } focus:outline-none focus:ring-2 focus:ring-cyan-400`
              }
            >
              <Icon className="w-5 h-5" aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
