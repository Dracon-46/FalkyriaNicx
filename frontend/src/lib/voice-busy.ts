import { create } from 'zustand';
import { reportVoiceBusy } from './api';
import { useTtsStore } from './tts';

/**
 * Keeps the background "Nicx, ligar" listener quiet while this window is in a
 * voice conversation or Nicx is talking, so it never wakes up on Nicx's own
 * voice. The server holds the flag with a short validity that this window
 * renews while busy: a tab that closes without saying goodbye stops counting
 * on its own.
 */

/** How often a busy window renews the flag, and how long the server keeps it. */
export const HEARTBEAT_MS = 4000;
export const BUSY_TTL_S = 10;

interface VoiceActivity {
  /** Hands-free conversations running in this window, by owner. */
  conversations: Record<string, true>;
  setConversationActive: (owner: string, active: boolean) => void;
}

export const useVoiceActivity = create<VoiceActivity>((set) => ({
  conversations: {},
  setConversationActive: (owner, active) =>
    set((state) => {
      if (active === Boolean(state.conversations[owner])) return state;
      const conversations = { ...state.conversations };
      if (active) conversations[owner] = true;
      else delete conversations[owner];
      return { conversations };
    }),
}));

export function isVoiceBusy(): boolean {
  return (
    Object.keys(useVoiceActivity.getState().conversations).length > 0
    || useTtsStore.getState().state !== 'idle'
  );
}

export interface BusyReporterOptions {
  /** Identifies this window to the server (one flag per window). */
  source?: string;
  /** The floating mascot counts as busy for as long as it is open. */
  alwaysBusy?: boolean;
  report?: (source: string, busy: boolean, ttl: number) => Promise<void>;
}

/** Start reporting; returns the function that stops (and clears the flag). */
export function startVoiceBusyReporter(options: BusyReporterOptions = {}): () => void {
  const source = options.source ?? `interface-${Math.random().toString(36).slice(2, 10)}`;
  const report = options.report ?? reportVoiceBusy;
  const send = (busy: boolean) => {
    report(source, busy, BUSY_TTL_S).catch(() => {
      // Server offline: there is no listener to coordinate with either.
    });
  };

  let busy = false;
  let timer: ReturnType<typeof setInterval> | null = null;
  const update = () => {
    const now = options.alwaysBusy === true || isVoiceBusy();
    if (now === busy) return;
    busy = now;
    send(now);
    if (now) {
      timer = setInterval(() => send(true), HEARTBEAT_MS);
    } else if (timer) {
      clearInterval(timer);
      timer = null;
    }
  };

  const unsubscribers = [useVoiceActivity.subscribe(update), useTtsStore.subscribe(update)];
  update();

  return () => {
    unsubscribers.forEach((unsubscribe) => unsubscribe());
    if (timer) clearInterval(timer);
    timer = null;
    if (busy) send(false);
    busy = false;
  };
}
