import React from 'react';

export function SkipToContent() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-cyan-500 focus:text-slate-950 focus:font-bold focus:rounded-md focus:shadow-lg focus:outline-none focus:ring-4 focus:ring-white"
    >
      Skip to main content
    </a>
  );
}
