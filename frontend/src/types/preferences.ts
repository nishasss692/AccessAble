/**
 * Schema types for Accessibility Preferences matching backend FastAPI schemas.
 */

export type TextScaleType = 'small' | 'medium' | 'large';

export interface PreferencesResponse {
  visual_alerts_enabled: boolean;
  audio_alerts_enabled: boolean;
  high_contrast_enabled: boolean;
  text_scale: TextScaleType;
  updated_at: string; // ISO UTC string
}

export interface PreferencesUpdate {
  visual_alerts_enabled: boolean;
  audio_alerts_enabled: boolean;
  high_contrast_enabled: boolean;
  text_scale: TextScaleType;
}

export type RingConnectionStatus = 'connected' | 'disconnected' | 'error' | 'unknown';

export interface RingStatusResponse {
  source: string;
  status: RingConnectionStatus;
  is_connected: boolean;
  last_checked_at: string | null;
  last_successful_sync_at: string | null;
  error_message: string | null;
  details: {
    mode?: string;
    note?: string;
    demo_events_supported?: boolean;
    [key: string]: unknown;
  };
}
