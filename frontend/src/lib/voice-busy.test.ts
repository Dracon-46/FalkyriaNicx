import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({
  reportVoiceBusy: vi.fn(async () => {}),
  synthesizeSpeech: vi.fn(),
  fetchTtsHealth: vi.fn(),
}));

import { BUSY_TTL_S, HEARTBEAT_MS, startVoiceBusyReporter, useVoiceActivity } from './voice-busy';
import { useTtsStore } from './tts';

describe('startVoiceBusyReporter', () => {
  const report = vi.fn(async (_source: string, _busy: boolean, _ttl: number) => {});

  beforeEach(() => {
    vi.useFakeTimers();
    report.mockClear();
    useVoiceActivity.setState({ conversations: {} });
    useTtsStore.setState({ state: 'idle', speakingId: null });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('stays silent while nothing happens', () => {
    const stop = startVoiceBusyReporter({ source: 'aba', report });
    expect(report).not.toHaveBeenCalled();
    stop();
    expect(report).not.toHaveBeenCalled();
  });

  it('reports a voice conversation, renews it and clears it when it ends', () => {
    const stop = startVoiceBusyReporter({ source: 'aba', report });
    useVoiceActivity.getState().setConversationActive('chat', true);
    expect(report).toHaveBeenLastCalledWith('aba', true, BUSY_TTL_S);

    vi.advanceTimersByTime(HEARTBEAT_MS * 2);
    expect(report.mock.calls.filter(([, busy]) => busy)).toHaveLength(3);

    useVoiceActivity.getState().setConversationActive('chat', false);
    expect(report).toHaveBeenLastCalledWith('aba', false, BUSY_TTL_S);
    vi.advanceTimersByTime(HEARTBEAT_MS * 3);
    expect(report).toHaveBeenCalledTimes(4);
    stop();
  });

  it('counts Nicx speaking as busy (never wake on its own voice)', () => {
    const stop = startVoiceBusyReporter({ source: 'aba', report });
    useTtsStore.setState({ state: 'speaking', speakingId: 'm1' });
    expect(report).toHaveBeenLastCalledWith('aba', true, BUSY_TTL_S);
    useTtsStore.setState({ state: 'idle', speakingId: null });
    expect(report).toHaveBeenLastCalledWith('aba', false, BUSY_TTL_S);
    stop();
  });

  it('clears the flag when stopped while busy', () => {
    const stop = startVoiceBusyReporter({ source: 'mascote', report, alwaysBusy: true });
    expect(report).toHaveBeenLastCalledWith('mascote', true, BUSY_TTL_S);
    stop();
    expect(report).toHaveBeenLastCalledWith('mascote', false, BUSY_TTL_S);
    vi.advanceTimersByTime(HEARTBEAT_MS * 3);
    expect(report).toHaveBeenCalledTimes(2);
  });
});
