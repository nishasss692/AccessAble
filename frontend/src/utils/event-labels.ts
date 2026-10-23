/**
 * Labels and badges for events to clearly distinguish Demo vs Real Ring Hardware events.
 */

export function isDemoEvent(source: string): boolean {
  return source.toLowerCase() === 'demo';
}

export function getSourceBadgeInfo(source: string) {
  const isDemo = isDemoEvent(source);
  if (isDemo) {
    return {
      label: 'SIMULATED DEMO',
      description: 'Simulated alert for demonstration and accessibility testing. Not live Ring hardware.',
      bgClass: 'bg-amber-500/20 text-amber-300 border-amber-500/50',
      iconClass: 'text-amber-400',
      isLive: false,
    };
  }
  return {
    label: 'LIVE RING DEVICE',
    description: 'Actual hardware event received from connected Ring doorbell/camera.',
    bgClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50',
    iconClass: 'text-cyan-400',
    isLive: true,
  };
}

export function formatEventType(type: string): string {
  switch (type.toLowerCase()) {
    case 'doorbell_ring':
    case 'doorbell_press':
      return 'Doorbell Chime / Press';
    case 'motion':
      return 'Motion Detected';
    case 'person':
      return 'Person Detected';
    case 'package':
      return 'Package Detected';
    default:
      return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
