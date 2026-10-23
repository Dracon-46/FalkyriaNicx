import { useAppStore } from './store';
import { useTtsStore } from './tts';
import { stripThinkTags } from './message-text';
import type { SilenceOptions } from './audio-level';

/** Where the hands-free loop is: listen → transcribe → think → speak → listen. */
export type ConversationPhase = 'off' | 'listening' | 'transcribing' | 'thinking' | 'speaking';

/** What sending one transcribed message led to. */
export type SendOutcome = 'done' | 'stopped' | 'not-sent';

export const CONVERSATION_PHASE_LABEL: Record<ConversationPhase, string> = {
  off: 'Conversa por voz',
  listening: 'Ouvindo…',
  transcribing: 'Transcrevendo…',
  thinking: 'Pensando…',
  speaking: 'Falando…',
};

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
}

/** Quiet time that ends an utterance, and how long one listening round lasts. */
export const SILENCE_MS = 1300;
export const ROUND_MS = 15000;
/** Silent rounds in a row (about a minute) before the mode switches itself off. */
export const MAX_IDLE_ROUNDS = 4;

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
    const wasSpeaking = this.current === 'speaking';
    this.setPhase('off');
    this.deps.speech().cancelRecording();
    if (wasSpeaking) useTtsStore.getState().stop();
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
        this.stop('Conversa por voz encerrada: ninguém falou por um minuto.');
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
    const before = lastAssistant()?.id;
    const outcome = await this.deps.send(text);
    if (!this.alive(session)) return;
    if (outcome === 'not-sent') {
      this.stop();
      return;
    }

    const reply = lastAssistant();
    const spoken =
      reply && reply.id !== before && outcome === 'done' ? stripThinkTags(reply.content) : '';
    if (reply && spoken) {
      await useTtsStore.getState().ensureHealth();
      if (!this.alive(session)) return;
      const tts = useTtsStore.getState();
      if (tts.available === true) {
        this.setPhase('speaking');
        // Autoplay (Settings) may have picked this reply up already; never
        // read it twice.
        if (tts.speakingId !== reply.id && tts.autoSpokenId !== reply.id) {
          tts.markAutoSpoken(reply.id);
          void tts.speak(reply.id, spoken);
        }
        await waitForSpeechToEnd(reply.id);
      }
    }

    await this.listen(session, 0);
  }
}
