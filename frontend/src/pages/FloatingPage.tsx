import { useCallback, useEffect, useRef, useState } from 'react';
import { X, Mic } from 'lucide-react';
import { toast } from 'sonner';
import { NicxMascot } from '../components/Mascot/NicxMascot';
import { Toaster } from '../components/ui/sonner';
import { useSpeech } from '../hooks/useSpeech';
import { useVoiceConversation, type SendOutcome } from '../hooks/useVoiceConversation';
import { useAppStore } from '../lib/store';
import { useTtsStore } from '../lib/tts';
import { bindMascotToChat } from '../lib/mascot-chat';
import { startVoiceBusyReporter } from '../lib/voice-busy';
import { stripThinkTags } from '../lib/message-text';
import { ensureModels, sendSpokenMessage } from '../lib/spoken-chat';
import {
  closeFloatingWindow,
  isFarewell,
  notifyFloatingProblem,
  notifyFloatingReady,
} from '../lib/floating';

/** Longest goodbye wait before the window closes anyway. */
const GOODBYE_MS = 5000;

function waitForTtsIdle(timeoutMs: number): Promise<void> {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      unsubscribe();
      resolve();
    };
    const timer = setTimeout(done, timeoutMs);
    const unsubscribe = useTtsStore.subscribe((s) => {
      if (s.state === 'idle') done();
    });
  });
}

/**
 * The mascot that "Nicx, ligar" brings up: a small always-on-top window
 * (or a browser tab, as a fallback) that starts a hands-free voice
 * conversation by itself and closes when it ends -- after a minute of
 * silence, on "Nicx, tchau" / "desligar", or with the close button.
 */
export default function FloatingPage() {
  const speech = useSpeech();
  const conversationId = useRef<string | null>(null);
  const closing = useRef(false);
  const wasActive = useRef(false);
  const announced = useRef(false);
  const [ended, setEnded] = useState(false);

  const messages = useAppStore((s) => s.messages);
  const streaming = useAppStore((s) => s.streamState.isStreaming);
  const streamText = useAppStore((s) => s.streamState.content);

  const goodbyeRef = useRef<() => void>(() => {});
  const send = useCallback(async (text: string): Promise<SendOutcome> => {
    if (isFarewell(text)) {
      goodbyeRef.current();
      return 'stopped';
    }
    return sendSpokenMessage(text, {
      conversationId: conversationId.current,
      onConversation: (id) => {
        conversationId.current = id;
      },
    });
  }, []);
  const conversation = useVoiceConversation(speech, send);
  const conversationRef = useRef(conversation);
  conversationRef.current = conversation;

  const finish = useCallback(async () => {
    closing.current = true;
    conversationRef.current.stop();
    useTtsStore.getState().stop();
    if (!(await closeFloatingWindow())) setEnded(true);
  }, []);

  goodbyeRef.current = () => {
    closing.current = true;
    conversationRef.current.stop();
    void (async () => {
      await useTtsStore.getState().ensureHealth();
      if (useTtsStore.getState().available) {
        void useTtsStore.getState().speak('nicx-tchau', 'Até logo!');
        await waitForTtsIdle(GOODBYE_MS);
      }
      if (!(await closeFloatingWindow())) setEnded(true);
    })();
  };

  const listen = useCallback(() => {
    closing.current = false;
    setEnded(false);
    conversationRef.current.start();
  }, []);

  useEffect(() => {
    if (!speech.error) return;
    toast.error(speech.error, { duration: 8000 });
    void notifyFloatingProblem(speech.error);
  }, [speech.error]);

  // The microphone is really open: tell the host (it logs the wake latency).
  useEffect(() => {
    if (speech.state === 'recording' && !announced.current) {
      announced.current = true;
      void notifyFloatingReady();
    }
  }, [speech.state]);

  // Mood follows the replies; the listener stays quiet while this is open.
  useEffect(() => bindMascotToChat(), []);
  useEffect(() => startVoiceBusyReporter({ source: 'mascote' }), []);

  // Start listening as soon as a model is known.
  useEffect(() => {
    let cancelled = false;
    void ensureModels().finally(() => {
      if (!cancelled) conversationRef.current.start();
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // When the conversation ends by itself (a silent minute), the window goes away.
  useEffect(() => {
    if (conversation.active) {
      wasActive.current = true;
      return;
    }
    if (wasActive.current && !closing.current) {
      wasActive.current = false;
      // Never got to listen (no microphone...): stay open to show why.
      if (announced.current) void finish();
      else setEnded(true);
    }
  }, [conversation.active, finish]);

  const lastUser = [...messages].reverse().find((m) => m.role === 'user');
  const lastReply = messages[messages.length - 1]?.role === 'assistant'
    ? messages[messages.length - 1]
    : undefined;
  const replyText = stripThinkTags(streaming ? streamText : lastReply?.content ?? '').trim();

  return (
    <div
      className="flex h-screen flex-col overflow-hidden select-none"
      style={{ background: 'var(--color-bg)', color: 'var(--color-text)' }}
      data-testid="floating-page"
    >
      <header className="pywebview-drag-region flex items-center justify-between px-3 py-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold">
          Nicx
          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: '#eda100' }} />
        </span>
        <button
          type="button"
          onClick={() => void finish()}
          aria-label="Fechar"
          title="Fechar"
          className="rounded-md p-1 cursor-pointer"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          <X size={16} />
        </button>
      </header>

      <main className="flex flex-1 flex-col items-center gap-2 px-4 min-h-0">
        <NicxMascot size={140} />
        <div
          className="text-sm font-medium"
          style={{ color: conversation.active ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}
          aria-live="polite"
        >
          {ended ? 'Conversa encerrada' : conversation.active ? conversation.label : 'Preparando…'}
        </div>

        <div
          className="w-full flex-1 min-h-0 overflow-y-auto text-xs leading-relaxed space-y-1.5"
          style={{ color: 'var(--color-text-secondary)' }}
          data-testid="floating-transcript"
        >
          {lastUser && (
            <p>
              <span style={{ color: 'var(--color-text-tertiary)' }}>Você: </span>
              {lastUser.content}
            </p>
          )}
          {replyText && (
            <p style={{ color: 'var(--color-text)' }}>
              <span style={{ color: 'var(--color-text-tertiary)' }}>Nicx: </span>
              {replyText}
            </p>
          )}
          {!lastUser && !ended && (
            <p className="text-center" style={{ color: 'var(--color-text-tertiary)' }}>
              Pode falar. Diga “tchau” para eu sair.
            </p>
          )}
        </div>
      </main>

      <footer className="px-4 pb-3 pt-2">
        {ended ? (
          <button
            type="button"
            onClick={listen}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg py-2 text-sm cursor-pointer"
            style={{ background: 'var(--color-accent)', color: 'var(--color-bg)' }}
          >
            <Mic size={14} /> Ouvir de novo
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void finish()}
            className="w-full rounded-lg py-2 text-sm cursor-pointer"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
          >
            Encerrar
          </button>
        )}
      </footer>
      <Toaster position="top-center" />
    </div>
  );
}
