import { useAppStore } from './store';
import { useMascot, type MascotMood } from './mascot';

type AppState = ReturnType<typeof useAppStore.getState>;
type MascotState = ReturnType<typeof useMascot.getState>;

interface Store<T> {
  getState: () => T;
  subscribe: (listener: (state: T, prev: T) => void) => () => void;
}

/** How long the mascot stays happy after a reply, or sad after a failure. */
export const HAPPY_MS = 1800;
export const ERROR_MS = 3200;

/**
 * Mirror the chat stream into the mascot's mood:
 * `thinking` while a reply streams, `happy` for a moment when it finishes,
 * `error` when it fails, then back to `idle`. A reply the user stopped just
 * returns to `idle`. Moods set elsewhere meanwhile (voice: `listening`,
 * `speaking`) are never overwritten when the timers expire.
 *
 * Failures are detected from the chat error log entries the send flow already
 * writes (`category: 'chat'`, `level: 'error'`), so no stream code changes.
 * Returns the unsubscribe function.
 */
export function bindMascotToChat(
  app: Store<AppState> = useAppStore,
  mascot: Store<MascotState> = useMascot,
): () => void {
  let streaming = app.getState().streamState.isStreaming;
  let failed = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const clearTimer = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };

  const showFor = (mood: MascotMood, ms: number) => {
    clearTimer();
    mascot.getState().setMood(mood);
    timer = setTimeout(() => {
      timer = null;
      if (mascot.getState().mood === mood) mascot.getState().setMood('idle');
    }, ms);
  };

  const unsubscribe = app.subscribe((state, prev) => {
    if (streaming && state.logEntries !== prev.logEntries) {
      const entry = state.logEntries[state.logEntries.length - 1];
      if (entry?.level === 'error' && entry.category === 'chat') failed = true;
    }

    const now = state.streamState.isStreaming;
    if (now === streaming) return;
    streaming = now;

    if (now) {
      clearTimer();
      failed = false;
      mascot.getState().setMood('thinking');
      return;
    }

    if (failed) {
      showFor('error', ERROR_MS);
      return;
    }
    // A finished reply is saved with its telemetry before the stream resets;
    // a reply the user stopped is not. Only judge what is on screen.
    const conversationId = prev.streamState.conversationId;
    const last = state.messages[state.messages.length - 1];
    const stopped =
      state.activeId === conversationId && (last?.role !== 'assistant' || !last.telemetry);
    if (stopped) {
      clearTimer();
      if (mascot.getState().mood === 'thinking') mascot.getState().setMood('idle');
    } else {
      showFor('happy', HAPPY_MS);
    }
  });

  return () => {
    unsubscribe();
    clearTimer();
  };
}
