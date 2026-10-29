import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { create } from 'zustand';
import type { ChatMessage, LogEntry, StreamState } from '../types';
import { useMascot } from './mascot';
import { bindMascotToChat, ERROR_MS, HAPPY_MS } from './mascot-chat';

interface FakeApp {
  activeId: string | null;
  messages: ChatMessage[];
  streamState: StreamState;
  logEntries: LogEntry[];
}

const IDLE_STREAM: StreamState = {
  conversationId: null,
  isStreaming: false,
  phase: '',
  elapsedMs: 0,
  activeToolCalls: [],
  content: '',
};

function setup() {
  const app = create<FakeApp>(() => ({
    activeId: 'c1',
    messages: [],
    streamState: IDLE_STREAM,
    logEntries: [],
  }));
  const unbind = bindMascotToChat(app as unknown as Parameters<typeof bindMascotToChat>[0]);

  const start = () =>
    app.setState({ streamState: { ...IDLE_STREAM, conversationId: 'c1', isStreaming: true } });
  const reply = (finished: boolean) =>
    app.setState({
      messages: [
        {
          id: 'a1',
          role: 'assistant',
          content: 'Oi!',
          timestamp: 0,
          telemetry: finished ? { engine: 'ollama', total_ms: 10 } : undefined,
        } as ChatMessage,
      ],
    });
  const end = () => app.setState({ streamState: IDLE_STREAM });
  const logError = () =>
    app.setState((s) => ({
      logEntries: [
        ...s.logEntries,
        { timestamp: 0, level: 'error', category: 'chat', message: 'Stream error: boom' },
      ],
    }));
  return { unbind, start, reply, end, logError };
}

const mood = () => useMascot.getState().mood;

describe('bindMascotToChat', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useMascot.getState().setMood('idle');
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('thinks while streaming, cheers when the reply finishes, then rests', () => {
    const { unbind, start, reply, end } = setup();

    start();
    expect(mood()).toBe('thinking');
    reply(true);
    end();
    expect(mood()).toBe('happy');
    vi.advanceTimersByTime(HAPPY_MS);
    expect(mood()).toBe('idle');
    unbind();
  });

  it('shows the error mood when the stream logs a chat error', () => {
    const { unbind, start, reply, end, logError } = setup();

    start();
    logError();
    reply(true);
    end();
    expect(mood()).toBe('error');
    vi.advanceTimersByTime(ERROR_MS);
    expect(mood()).toBe('idle');
    unbind();
  });

  it('just rests when the user stops the reply', () => {
    const { unbind, start, reply, end } = setup();

    start();
    reply(false);
    end();
    expect(mood()).toBe('idle');
    unbind();
  });

  it('never overrides a mood the voice code set in the meantime', () => {
    const { unbind, start, reply, end } = setup();

    start();
    reply(true);
    end();
    useMascot.getState().setMood('speaking');
    vi.advanceTimersByTime(HAPPY_MS);
    expect(mood()).toBe('speaking');
    unbind();
  });

  it('keeps speaking when the reply finishes while its first sentences are spoken', () => {
    const { unbind, start, reply, end } = setup();

    start();
    useMascot.getState().setMood('speaking');
    reply(true);
    end();
    expect(mood()).toBe('speaking');
    vi.advanceTimersByTime(HAPPY_MS);
    expect(mood()).toBe('speaking');
    unbind();
  });
});
