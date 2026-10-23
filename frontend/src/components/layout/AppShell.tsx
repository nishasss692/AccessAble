import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileNavigation } from './MobileNavigation';
import { SkipToContent } from '../accessibility/SkipToContent';

export function AppShell() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 futuristic-grid">
      {/* Invisible screen pulse layer for visual alert notifications */}
      <div
        id="visual-alert-pulse"
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-50 bg-cyan-400/20 border-8 border-cyan-400 opacity-0 transition-opacity duration-300"
      />

      <SkipToContent />
      <Header />

      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        <Sidebar />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 p-4 sm:p-6 lg:p-8 pb-20 md:pb-8 focus:outline-none overflow-y-auto"
        >
          <Outlet />
        </main>
      </div>

      <MobileNavigation />
    </div>
  );
}
