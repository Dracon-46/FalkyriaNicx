import { create } from 'zustand';
import { synthesizeSpeech, fetchTtsHealth } from './api';
import { toSpeakableText } from './message-text';
import { useMascot } from './mascot';
import { LEVEL_FPS, LEVEL_INTERVAL_MS, wavEnvelope } from './audio-level';
import { SentenceSplitter, splitSentences } from './sentence-splitter';
import { SpeechQueue } from './speech-queue';
import i18n from '../i18n';

export type TtsState = 'idle' | 'loading' | 'speaking';

/**
 * A reply being spoken while it is still written: feed it the whole text so
 * far with `update()`; each finished sentence is synthesized and queued.
 * `end()` speaks what is left; `cancel()` silences it.
 */
export interface SpeechStream {
  update: (fullText: string) => void;
  end: (fullText?: string) => void;
  cancel: () => void;
}

/**
 * Voice output is a single shared resource: one utterance at a time, for the
 * whole app. The state lives in one store rather than per component, because a
 * per-component hook would give every message its own audio element -- two
 * replies would then talk over each other, and autoplay would make that the
 * normal case rather than the exception.
 *
 * An utterance is spoken sentence by sentence (see SpeechQueue): the first
 * sentence plays while the next ones are synthesized, so the voice starts
 * long before the whole text is synthesized -- or, with `beginStream`, before
 * the model has even finished writing it.
 */
interface TtsStore {
  /** `loading` until the first sentence plays, `speaking` until the last one ends. */
  state: TtsState;
  /** id of the message currently loading or speaking, if any. */
  speakingId: string | null;
  error: string | null;
  /** Message whose read-aloud attempt failed, if any. */
  errorId: string | null;
  /** null until the health probe has answered. */
  available: boolean | null;
  /** Last message spoken by autoplay, so a re-render never repeats it. */
  autoSpokenId: string | null;
  /** Speak a finished text; resolves once the voice has started (or failed). */
  speak: (id: string, text: string) => Promise<void>;
  /** Speak a reply that is still streaming (see SpeechStream). */
  beginStream: (id: string) => SpeechStream;
  stop: () => void;
  ensureHealth: () => Promise<void>;
  markAutoSpoken: (id: string) => void;
}

// Playback handles are not render state -- keeping them out of the store avoids
// re-rendering every subscriber when an audio element is swapped.
let audio: HTMLAudioElement | null = null;
let objectUrl: string | null = null;
let queue: SpeechQueue<Blob> | null = null;
let token = 0;
let healthProbe: Promise<void> | null = null;
let levelTimer: ReturnType<typeof setInterval> | null = null;

/**
 * While a sentence plays, the mascot is `speaking` and its level follows the
 * audio: the WAV's loudness envelope is precomputed and looked up from
 * `currentTime`, so playback never has to go through Web Audio. Until the
 * envelope is ready (or if the audio is not a readable WAV) a gentle wobble
 * stands in.
 */
function startSpeakingMood(el: HTMLAudioElement, blob: Blob, mine: number): void {
  stopSpeakingLevels();
  useMascot.getState().setMood('speaking');

  let envelope: number[] | null = null;
  blob
    .arrayBuffer()
    .then((buf) => {
      if (mine === token) envelope = wavEnvelope(buf);
    })
    .catch(() => {});

  const started = Date.now();
  levelTimer = setInterval(() => {
    const t = Number.isFinite(el.currentTime) ? el.currentTime : (Date.now() - started) / 1000;
    const level = envelope
      ? (envelope[Math.floor(t * LEVEL_FPS)] ?? 0)
      : 0.35 + 0.25 * Math.sin(t * 14) * Math.sin(t * 3.1);
    useMascot.getState().setLevel(level);
  }, LEVEL_INTERVAL_MS);
}

function stopSpeakingLevels(): void {
  if (levelTimer) {
    clearInterval(levelTimer);
    levelTimer = null;
  }
}

/** Leave the mascot alone if the chat flow changed its mood meanwhile. */
function endSpeakingMood(): void {
  stopSpeakingLevels();
  const mascot = useMascot.getState();
  if (mascot.mood === 'speaking') mascot.setMood('idle');
}

/** Only a stream ending in the active conversation may trigger autoplay. */
export function shouldAutoplayFinishedReply(
  previousStreamingConversationId: string | null,
  activeId: string | null,
  streamIsActive: boolean,
  lastMessage: { id: string; role: string } | undefined,
  autoSpokenId: string | null,
): boolean {
  return previousStreamingConversationId !== null
    && previousStreamingConversationId === activeId
    && !streamIsActive
    && lastMessage !== undefined
    && lastMessage.role === 'assistant'
    && lastMessage.id !== autoSpokenId;
}

function releaseAudio(): void {
  if (audio) {
    // Detach first: clearing src re-runs the media load algorithm, which fails
    // on an empty source and dispatches an `error` event. With the handler
    // still attached that surfaces as a bogus "Playback failed" after every
    // successful utterance.
    audio.onended = null;
    audio.onerror = null;
    audio.pause();
    audio.src = '';
    audio = null;
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
}

function teardown(): void {
  endSpeakingMood();
  // Cancelling aborts the syntheses in flight and the clip playing.
  if (queue) {
    queue.cancel();
    queue = null;
  }
  releaseAudio();
}

/**
 * Play one sentence. Resolves when it ends or the queue is cancelled; rejects
 * if the browser cannot play it. Between sentences the mascot keeps its
 * `speaking` pose with the level at rest.
 */
function playClip(blob: Blob, signal: AbortSignal, mine: number, onStart: () => void): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const url = URL.createObjectURL(blob);
    const el = new Audio(url);
    releaseAudio();
    audio = el;
    objectUrl = url;
    let settled = false;

    const cleanup = () => {
      settled = true;
      signal.removeEventListener('abort', onAbort);
      stopSpeakingLevels();
      if (useMascot.getState().mood === 'speaking') useMascot.getState().setLevel(0);
      if (audio === el) {
        releaseAudio();
      } else {
        el.onended = null;
        el.onerror = null;
        el.pause();
        URL.revokeObjectURL(url);
      }
    };
    const onAbort = () => {
      if (settled) return;
      cleanup();
      resolve();
    };
    signal.addEventListener('abort', onAbort);

    el.onended = () => {
      cleanup();
      resolve();
    };
    el.onerror = () => {
      cleanup();
      reject(new Error(i18n.t('errors.playbackFailed')));
    };
    el.play().then(
      () => {
        if (settled || mine !== token) return;
        if (useTtsStore.getState().state !== 'speaking') useTtsStore.setState({ state: 'speaking' });
        startSpeakingMood(el, blob, mine);
        onStart();
      },
      (err: unknown) => {
        if (settled) return;
        cleanup();
        reject(err instanceof Error ? err : new Error(i18n.t('errors.playbackFailed')));
      },
    );
  });
}

export const useTtsStore = create<TtsStore>((set, get) => {
  /**
   * Replace whatever is speaking with a new, empty queue for message `id`.
   * `started` resolves once the first sentence plays, or when the queue ends
   * without playing (nothing to say, cancelled, failed).
   */
  const open = (id: string) => {
    // Bump before teardown so a synthesis still in flight is both aborted and
    // fenced off by the token, even if the abort loses the race.
    token += 1;
    const mine = token;
    teardown();
    set({ state: 'loading', speakingId: id, error: null, errorId: null });

    let markStarted!: () => void;
    const started = new Promise<void>((resolve) => {
      markStarted = resolve;
    });
    const q = new SpeechQueue<Blob>({
      synthesize: (text, signal) => synthesizeSpeech(text, { signal }),
      play: (blob, signal) => playClip(blob, signal, mine, markStarted),
    });
    queue = q;

    q.finished.then(
      (result) => {
        if (mine === token && result === 'done') {
          queue = null;
          teardown();
          set({ state: 'idle', speakingId: null });
        }
        markStarted();
      },
      (err: unknown) => {
        if (mine === token && !(err instanceof DOMException && err.name === 'AbortError')) {
          queue = null;
          teardown();
          set({
            state: 'idle',
            speakingId: null,
            error: err instanceof Error && err.message ? err.message : i18n.t('errors.synthesisFailed'),
            errorId: id,
          });
        }
        markStarted();
      },
    );
    return { queue: q, mine, started };
  };

  /** Queue raw sentences, skipping any that have nothing to say aloud. */
  const feed = (q: SpeechQueue<Blob>, sentences: string[]) => {
    for (const sentence of sentences) {
      const spoken = toSpeakableText(sentence);
      if (spoken) q.push(spoken);
    }
  };

  return {
    state: 'idle',
    speakingId: null,
    error: null,
    errorId: null,
    available: null,
    autoSpokenId: null,

    ensureHealth: () => {
      if (healthProbe) return healthProbe;
      healthProbe = fetchTtsHealth()
        .then((health) => {
          set({ available: health.available });
          if (!health.available) healthProbe = null;
        })
        .catch(() => {
          set({ available: false });
          healthProbe = null;
        });
      return healthProbe;
    },

    markAutoSpoken: (id: string) => set({ autoSpokenId: id }),

    speak: async (id: string, text: string) => {
      const sentences = splitSentences(text).map(toSpeakableText).filter(Boolean);
      if (sentences.length === 0) return;
      const { queue: q, started } = open(id);
      sentences.forEach((s) => q.push(s));
      q.close();
      await started;
    },

    beginStream: (id: string): SpeechStream => {
      const { queue: q, mine } = open(id);
      const splitter = new SentenceSplitter();
      return {
        update: (fullText: string) => {
          if (mine === token) feed(q, splitter.update(fullText));
        },
        end: (fullText?: string) => {
          if (mine !== token) return;
          feed(q, splitter.finish(fullText));
          q.close();
        },
        cancel: () => {
          if (mine === token) get().stop();
        },
      };
    },

    stop: () => {
      token += 1;
      teardown();
      set({ state: 'idle', speakingId: null, error: null, errorId: null });
    },
  };
});

/** Test seam: reset module-level playback handles between cases. */
export function __resetTtsForTests(): void {
  teardown();
  token = 0;
  healthProbe = null;
  useTtsStore.setState({
    state: 'idle',
    speakingId: null,
    error: null,
    errorId: null,
    available: null,
    autoSpokenId: null,
  });
}
