import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  messages: [] as Array<{ id: string; role: string; content: string }>,
  spoken: [] as Array<[string, string]>,
}));

vi.mock('./store', () => ({
  useAppStore: { getState: () => ({ messages: h.messages }) },
}));

vi.mock('./tts', async () => {
  const { create } = await import('zustand');
  interface FakeTts {
    state: 'idle' | 'loading' | 'speaking';
    speakingId: string | null;
    available: boolean | null;
    autoSpokenId: string | null;
    ensureHealth: () => Promise<void>;
    markAutoSpoken: (id: string) => void;
    speak: (id: string, text: string) => Promise<void>;
    stop: () => void;
  }
  const useTtsStore = create<FakeTts>((set) => ({
    state: 'idle',
    speakingId: null,
    available: true,
    autoSpokenId: null,
    ensureHealth: async () => {},
    markAutoSpoken: (id) => set({ autoSpokenId: id }),
    speak: async (id, text) => {
      h.spoken.push([id, text]);
      set({ state: 'speaking', speakingId: id });
    },
    stop: () => set({ state: 'idle', speakingId: null }),
  }));
  return { useTtsStore };
});

import { useTtsStore } from './tts';
import {
  MAX_IDLE_ROUNDS,
  VoiceConversation,
  type ConversationPhase,
  type SendOutcome,
} from './voice-conversation';

type OnSilence = (heard: boolean) => void;

function setup(opts: { transcript?: string; outcome?: SendOutcome; startOk?: boolean } = {}) {
  const phases: ConversationPhase[] = [];
  const notices: string[] = [];
  const silences: OnSilence[] = [];
  const speech = {
    startRecording: vi.fn(async (o?: { onSilence?: OnSilence }) => {
      if (o?.onSilence) silences.push(o.onSilence);
      return opts.startOk ?? true;
    }),
    stopRecording: vi.fn(async () => opts.transcript ?? 'Que horas são?'),
    cancelRecording: vi.fn(),
  };
  const send = vi.fn(async (text: string): Promise<SendOutcome> => {
    const outcome = opts.outcome ?? 'done';
    if (outcome !== 'not-sent') {
      h.messages.push({ id: `u${h.messages.length}`, role: 'user', content: text });
      h.messages.push({ id: `a${h.messages.length}`, role: 'assistant', content: 'São <b>dez</b> horas.' });
    }
    return outcome;
  });
  const convo = new VoiceConversation({
    speech: () => speech,
    send,
    onPhase: (p) => phases.push(p),
    notify: (m) => notices.push(m),
  });
  const lastSilence = () => silences[silences.length - 1];
  return { convo, speech, send, phases, notices, silences, lastSilence };
}

beforeEach(() => {
  h.messages.length = 0;
  h.spoken.length = 0;
  useTtsStore.setState({ state: 'idle', speakingId: null, available: true, autoSpokenId: null });
});

describe('hands-free voice conversation', () => {
  it('listens, sends the transcript, speaks the reply and listens again', async () => {
    const t = setup();
    t.convo.start();
    await vi.waitFor(() => expect(t.silences).toHaveLength(1));
    expect(t.convo.phase).toBe('listening');

    t.lastSilence()(true);
    await vi.waitFor(() => expect(t.convo.phase).toBe('speaking'));
    expect(t.send).toHaveBeenCalledWith('Que horas são?');
    const reply = h.messages[h.messages.length - 1];
    expect(h.spoken).toEqual([[reply.id, reply.content]]);
    expect(useTtsStore.getState().autoSpokenId).toBe(reply.id);

    // Playback ends: back to listening, with a fresh recording.
    useTtsStore.setState({ state: 'idle', speakingId: null });
    await vi.waitFor(() => expect(t.silences).toHaveLength(2));
    expect(t.convo.phase).toBe('listening');
    expect(t.phases).toEqual(['listening', 'transcribing', 'thinking', 'speaking', 'listening']);
  });

  it('does not read a reply twice when autoplay already spoke it', async () => {
    const t = setup();
    t.convo.start();
    await vi.waitFor(() => expect(t.silences).toHaveLength(1));
    t.send.mockImplementationOnce(async (text: string) => {
      h.messages.push({ id: 'u', role: 'user', content: text });
      h.messages.push({ id: 'auto', role: 'assistant', content: 'Oi' });
      useTtsStore.setState({ autoSpokenId: 'auto' });
      return 'done';
    });

    t.lastSilence()(true);
    await vi.waitFor(() => expect(t.silences).toHaveLength(2));
    expect(h.spoken).toEqual([]);
  });

  it('keeps listening after an empty transcript without sending anything', async () => {
    const t = setup({ transcript: '   ' });
    t.convo.start();
    await vi.waitFor(() => expect(t.silences).toHaveLength(1));
    t.lastSilence()(true);
    await vi.waitFor(() => expect(t.silences).toHaveLength(2));
    expect(t.send).not.toHaveBeenCalled();
  });

  it('switches itself off after a minute of silence', async () => {
    const t = setup();
    t.convo.start();
    for (let round = 1; round <= MAX_IDLE_ROUNDS; round++) {
      await vi.waitFor(() => expect(t.silences).toHaveLength(round));
      t.lastSilence()(false);
    }
    await vi.waitFor(() => expect(t.convo.phase).toBe('off'));
    expect(t.speech.cancelRecording).toHaveBeenCalled();
    expect(t.notices).toHaveLength(1);
    expect(t.speech.startRecording).toHaveBeenCalledTimes(MAX_IDLE_ROUNDS);
  });

  it('stops when the message could not be sent (e.g. no model picked)', async () => {
    const t = setup({ outcome: 'not-sent' });
    t.convo.start();
    await vi.waitFor(() => expect(t.silences).toHaveLength(1));
    t.lastSilence()(true);
    await vi.waitFor(() => expect(t.convo.phase).toBe('off'));
    expect(h.spoken).toEqual([]);
  });

  it('does not speak a reply the user stopped, but keeps listening', async () => {
    const t = setup({ outcome: 'stopped' });
    t.convo.start();
    await vi.waitFor(() => expect(t.silences).toHaveLength(1));
    t.lastSilence()(true);
    await vi.waitFor(() => expect(t.silences).toHaveLength(2));
    expect(h.spoken).toEqual([]);
  });

  it('stop() cancels the loop wherever it is', async () => {
    const t = setup();
    let release!: (o: SendOutcome) => void;
    t.send.mockImplementationOnce(() => new Promise<SendOutcome>((r) => (release = r)));
    t.convo.start();
    await vi.waitFor(() => expect(t.silences).toHaveLength(1));
    t.lastSilence()(true);
    await vi.waitFor(() => expect(t.convo.phase).toBe('thinking'));

    t.convo.stop();
    expect(t.convo.phase).toBe('off');
    release('done');
    await new Promise((r) => setTimeout(r, 0));

    expect(t.speech.startRecording).toHaveBeenCalledTimes(1);
    expect(h.spoken).toEqual([]);
  });

  it('ends at once if the microphone cannot start', async () => {
    const t = setup({ startOk: false });
    t.convo.start();
    await vi.waitFor(() => expect(t.convo.phase).toBe('off'));
    expect(t.notices).toEqual([]);
  });
});
