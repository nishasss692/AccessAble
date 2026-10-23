/**
 * Accessibility sound and screen-reader assistance utilities.
 * Uses Web Audio API synthesize pleasant accessible chimes without external assets.
 */

class AudioAlertManager {
  private ctx: AudioContext | null = null;

  private getContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  playChime(type: 'doorbell' | 'motion' | 'alert' = 'alert') {
    try {
      const ctx = this.getContext();
      if (!ctx) return;

      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'doorbell') {
        // High-low two-tone doorbell chime
        osc.type = 'sine';
        osc.frequency.setValueAtTime(659.25, now); // E5
        osc.frequency.setValueAtTime(523.25, now + 0.15); // C5
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
        osc.start(now);
        osc.stop(now + 0.6);
      } else if (type === 'motion') {
        // Rapid pleasant ascending chirp
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.2);
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      } else {
        // High urgency notification beep
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, now); // D5
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      }
    } catch (e) {
      console.warn('Audio chime playback omitted or blocked by browser autoplay policy', e);
    }
  }
}

export const audioAlert = new AudioAlertManager();

/**
 * Trigger visual flashing pulse on document for photosensitive-safe visual alert.
 */
export function triggerVisualFlash() {
  if (typeof document === 'undefined') return;
  const overlay = document.getElementById('visual-alert-pulse');
  if (overlay) {
    overlay.classList.remove('opacity-0');
    overlay.classList.add('opacity-100');
    setTimeout(() => {
      overlay.classList.remove('opacity-100');
      overlay.classList.add('opacity-0');
    }, 400);
  }
}
