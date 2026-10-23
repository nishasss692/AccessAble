import React from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { EventsPage } from '../features/events/EventsPage';
import { PreferencesPage } from '../features/preferences/PreferencesPage';
import { RingConnectionPage } from '../features/integrations/RingConnectionPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: 'events',
        element: <EventsPage />,
      },
      {
        path: 'preferences',
        element: <PreferencesPage />,
      },
      {
        path: 'integration',
        element: <RingConnectionPage />,
      },
      {
        path: '*',
        element: <DashboardPage />,
      },
    ],
  },
]);
