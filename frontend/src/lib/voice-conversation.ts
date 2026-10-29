import { useAppStore } from './store';
import { useTtsStore, type SpeechStream } from './tts';
import { stripThinkTags } from './message-text';
import type { SilenceOptions } from './audio-level';
import i18n from '../i18n';

/** Where the hands-free loop is: listen → transcribe → think → speak → listen. */
export type ConversationPhase = 'off' | 'listening' | 'transcribing' | 'thinking' | 'speaking';

/** What sending one transcribed message led to. */
export type SendOutcome = 'done' | 'stopped' | 'not-sent';

/** What the voice-conversation button says in each phase, in the UI language. */
export function conversationPhaseLabel(phase: ConversationPhase): string {
  return i18n.t(`chat.voice.phase.${phase}`);
}

/** The microphone side, as `useSpeech` provides it. */
export interface SpeechControls {
  startRecording: (
    opts?: SilenceOptions & { onSilence?: (heardSpeech: boolean) => void },
  ) => Promise<boolean>;
  stopRecording: () => Promise<string>;
  cancelRecording: () => void;
}

export interface ConversationDeps {
  speech: () => SpeechControls;
  send: (text: string) => Promise<SendOutcome>;
  onPhase: (phase: ConversationPhase) => void;
  notify: (message: string) => void;
  /** Abort the reply being generated (stopping mid-reply cancels the stream too). */
  cancel?: () => void;
}

/** Quiet time that ends an utterance, and how long one listening round lasts. */
export const SILENCE_MS = 1300;
export const ROUND_MS = 15000;
/** Silent rounds in a row (about a minute) before the mode switches itself off. */
export const MAX_IDLE_ROUNDS = 4;
/**
 * Pause after Nicx speaks before the microphone opens again: without a
 * headset, the laptop mic picks up the end of its own voice from the speakers.
 */
export const ECHO_SETTLE_MS = 600;

/** Resolve once the shared voice output is no longer busy with message `id`. */
function waitForSpeechToEnd(id: string): Promise<void> {
  return new Promise((resolve) => {
    const finished = (s: ReturnType<typeof useTtsStore.getState>) =>
      s.speakingId !== id || s.state === 'idle';
    if (finished(useTtsStore.getState())) {
      resolve();
      return;
    }
    const unsubscribe = useTtsStore.subscribe((s) => {
      if (!finished(s)) return;
      unsubscribe();
      resolve();
    });
  });
}

function lastAssistant() {
  const { messages } = useAppStore.getState();
  const last = messages[messages.length - 1];
  return last?.role === 'assistant' ? last : undefined;
}

/**
 * Hands-free voice conversation: listen until the user goes quiet, send what
 * they said, read the reply aloud, then listen again -- until `stop()`.
 *
 * Every `start()` opens a session and every async step checks that its
 * session is still current, so stopping cancels the loop wherever it is.
 */
export class VoiceConversation {
  private session = 0;
  private current: ConversationPhase = 'off';
  private readonly deps: ConversationDeps;

  constructor(deps: ConversationDeps) {
    this.deps = deps;
  }

  get phase(): ConversationPhase {
    return this.current;
  }

  start(): void {
    if (this.current !== 'off') return;
    this.session += 1;
    // Never record Nicx's own voice.
    useTtsStore.getState().stop();
    void this.listen(this.session, 0);
  }

  stop(notice?: string): void {
    if (this.current === 'off') return;
    this.session += 1;
    // The reply may already be speaking while it is still being written.
    const busy = this.current === 'thinking' || this.current === 'speaking';
    this.setPhase('off');
    this.deps.speech().cancelRecording();
    if (busy) {
      useTtsStore.getState().stop();
      this.deps.cancel?.();
    }
    if (notice) this.deps.notify(notice);
  }

  private setPhase(phase: ConversationPhase): void {
    this.current = phase;
    this.deps.onPhase(phase);
  }

  private alive(session: number): boolean {
    return this.session === session;
  }

  private async listen(session: number, idleRounds: number): Promise<void> {
    if (!this.alive(session)) return;
    this.setPhase('listening');
    const ok = await this.deps.speech().startRecording({
      silenceMs: SILENCE_MS,
      noSpeechMs: ROUND_MS,
      onSilence: (heard) => void this.afterSilence(session, heard, idleRounds),
    });
    // useSpeech has already said why (no microphone, permission denied...).
    if (!ok && this.alive(session)) this.stop();
  }

  private async afterSilence(session: number, heard: boolean, idleRounds: number): Promise<void> {
    if (!this.alive(session)) return;
    const speech = this.deps.speech();

    if (!heard) {
      speech.cancelRecording();
      if (idleRounds + 1 >= MAX_IDLE_ROUNDS) {
        this.stop(i18n.t('chat.voice.endedIdle'));
        return;
      }
      await this.listen(session, idleRounds + 1);
      return;
    }

    this.setPhase('transcribing');
    let text: string;
    try {
      text = (await speech.stopRecording()).trim();
    } catch {
      // The transcription error is already on screen (useSpeech).
      if (this.alive(session)) this.stop();
      return;
    }
    if (!this.alive(session)) return;
    if (!text) {
      await this.listen(session, idleRounds);
      return;
    }

    this.setPhase('thinking');
    // Probe the voice first, so the reply can be spoken while it streams.
    await useTtsStore.getState().ensureHealth();
    if (!this.alive(session)) return;
    const before = lastAssistant()?.id;
    const live = this.speakWhileStreaming(session, before);
    let outcome: SendOutcome;
    try {
      outcome = await this.deps.send(text);
    } finally {
      live.detach();
    }
    if (!this.alive(session)) {
      live.cancel();
      return;
    }
    if (outcome === 'not-sent') {
      live.cancel();
      this.stop();
      return;
    }

    const reply = lastAssistant();
    const fresh = reply && reply.id !== before && outcome === 'done' ? reply : undefined;
    if (!fresh) live.cancel();
    const tts = useTtsStore.getState();
    if (fresh && tts.available === true) {
      let speaking = false;
      const stream = live.stream();
      if (stream) {
        // The final text may hold a last sentence with no full stop.
        speaking = true;
        stream.end(fresh.content);
      } else {
        // Nothing streamed (or autoplay got there first): speak the whole reply.
        const spoken = stripThinkTags(fresh.content);
        if (spoken) {
          speaking = true;
          // Autoplay (Settings) may have picked this reply up already; never
          // read it twice.
          if (tts.speakingId !== fresh.id && tts.autoSpokenId !== fresh.id) {
            tts.markAutoSpoken(fresh.id);
            void tts.speak(fresh.id, spoken);
          }
        }
      }
      if (speaking) {
        this.setPhase('speaking');
        await waitForSpeechToEnd(fresh.id);
        if (!this.alive(session)) return;
        await new Promise((resolve) => setTimeout(resolve, ECHO_SETTLE_MS));
      }
    }

    await this.listen(session, 0);
  }

  /**
   * While the reply streams, speak each sentence as soon as it is complete
   * (see SpeechStream): the voice starts on the first sentence instead of
   * after the whole reply. The phase turns to `speaking` when the voice does.
   */
  private speakWhileStreaming(session: number, before: string | undefined) {
    let stream: SpeechStream | null = null;
    let replyId: string | null = null;
    const handle = {
      stream: () => stream,
      detach: () => {},
      cancel: () => stream?.cancel(),
    };
    if (useTtsStore.getState().available !== true) return handle;

    const onText = (content: string) => {
      if (!this.alive(session) || !content) return;
      if (!stream) {
        const reply = lastAssistant();
        if (!reply || reply.id === before) return;
        const tts = useTtsStore.getState();
        if (tts.speakingId === reply.id || tts.autoSpokenId === reply.id) return;
        tts.markAutoSpoken(reply.id);
        replyId = reply.id;
        stream = tts.beginStream(reply.id);
      }
      stream.update(content);
    };
    const offText = useAppStore.subscribe((state, prev) => {
      const content = state.streamState.content;
      if (content !== prev.streamState.content) onText(content);
    });
    const offVoice = useTtsStore.subscribe((state) => {
      if (
        replyId !== null
        && state.speakingId === replyId
        && state.state === 'speaking'
        && this.alive(session)
        && this.current === 'thinking'
      ) {
        this.setPhase('speaking');
      }
    });
    handle.detach = () => {
      offText();
      offVoice();
    };
    return handle;
  }
}
