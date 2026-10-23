/**
 * Labels and badge styles for connection and action statuses.
 */

import { RingConnectionStatus } from '../types/preferences';

export function getRingStatusBadge(status: RingConnectionStatus) {
  switch (status) {
    case 'connected':
      return {
        label: 'Online / Connected',
        description: 'Ring hardware stream is verified and actively monitoring.',
        color: 'emerald',
        bgClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50',
      };
    case 'disconnected':
      return {
        label: 'Disconnected',
        description: 'Ring credentials configured, but hardware connection is temporarily lost.',
        color: 'rose',
        bgClass: 'bg-rose-500/20 text-rose-300 border-rose-500/50',
      };
    case 'error':
      return {
        label: 'Connection Error',
        description: 'Authentication or network error communicating with Ring service.',
        color: 'rose',
        bgClass: 'bg-rose-500/20 text-rose-300 border-rose-500/50',
      };
    case 'unknown':
    default:
      return {
        label: 'Simulated Mode / Unconfigured',
        description: 'Live Ring hardware credentials not configured. Operating in local demo simulation mode.',
        color: 'cyan',
        bgClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50',
      };
  }
}

export function getActionBadge(action: 'acknowledged' | 'dismissed') {
  if (action === 'acknowledged') {
    return {
      label: 'Acknowledged',
      bgClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50',
    };
  }
  return {
    label: 'Dismissed',
    bgClass: 'bg-slate-500/20 text-slate-300 border-slate-500/50',
  };
}
