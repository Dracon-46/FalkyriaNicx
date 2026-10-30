// @vitest-environment happy-dom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  startRecording: vi.fn(),
  stopRecording: vi.fn(),
  cancelRecording: vi.fn(),
  sendSpokenMessage: vi.fn(),
  closeFloatingWindow: vi.fn(),
  notifyFloatingReady: vi.fn(),
  notifyFloatingProblem: vi.fn(),
  recording: false,
  reportVoiceBusy: vi.fn(),
  onSilence: null as null | ((heard: boolean) => void),
  dictation: 'desligado' as string | null,
}));

vi.mock('../lib/dictation', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/dictation')>()),
  useDictationState: () => mocks.dictation,
}));

vi.mock('../hooks/useSpeech', () => ({
  useSpeech: () => ({
    state: mocks.recording ? 'recording' : 'idle',
    error: null,
    available: true,
    startRecording: mocks.startRecording,
    stopRecording: mocks.stopRecording,
    cancelRecording: mocks.cancelRecording,
    isRecording: false,
    isTranscribing: false,
  }),
}));

vi.mock('../lib/spoken-chat', () => ({
  ensureModels: vi.fn(async () => {}),
  sendSpokenMessage: mocks.sendSpokenMessage,
}));

vi.mock('../lib/floating', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/floating')>()),
  closeFloatingWindow: mocks.closeFloatingWindow,
  notifyFloatingReady: mocks.notifyFloatingReady,
  notifyFloatingProblem: mocks.notifyFloatingProblem,
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api')>()),
  reportVoiceBusy: mocks.reportVoiceBusy,
  fetchTtsHealth: vi.fn(async () => ({ available: false })),
}));

import FloatingPage from './FloatingPage';

describe('FloatingPage (/flutuante)', () => {
  beforeEach(() => {
    mocks.onSilence = null;
    mocks.recording = false;
    mocks.dictation = 'desligado';
    mocks.startRecording.mockReset().mockImplementation(async (opts) => {
      mocks.onSilence = opts?.onSilence ?? null;
      mocks.recording = true;
      return true;
    });
    mocks.stopRecording.mockReset();
    mocks.cancelRecording.mockReset();
    mocks.sendSpokenMessage.mockReset().mockResolvedValue('done');
    mocks.closeFloatingWindow.mockReset().mockResolvedValue(true);
    mocks.notifyFloatingReady.mockReset().mockResolvedValue(undefined);
    mocks.reportVoiceBusy.mockReset().mockResolvedValue(undefined);
  });

  afterEach(() => cleanup());

  it('shows the mascot and starts the voice conversation by itself', async () => {
    const { rerender } = render(<FloatingPage />);

    expect(screen.getByTestId('floating-page')).toBeTruthy();
    expect(screen.getByRole('img', { name: /Nicx/ })).toBeTruthy();
    await waitFor(() => expect(mocks.startRecording).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText('Ouvindo…')).toBeTruthy());
    // The host hears "ready" only once the microphone is really recording.
    rerender(<FloatingPage />);
    await waitFor(() => expect(mocks.notifyFloatingReady).toHaveBeenCalledTimes(1));
    // The background listener is told to stay quiet meanwhile.
    expect(mocks.reportVoiceBusy).toHaveBeenCalledWith('mascote', true, expect.any(Number));
  });

  it('sends what was said and keeps the transcript on screen', async () => {
    mocks.stopRecording.mockResolvedValue('Que horas são?');
    render(<FloatingPage />);
    await waitFor(() => expect(mocks.onSilence).not.toBeNull());

    await act(async () => mocks.onSilence?.(true));

    await waitFor(() =>
      expect(mocks.sendSpokenMessage).toHaveBeenCalledWith('Que horas são?', expect.any(Object)),
    );
    expect(mocks.closeFloatingWindow).not.toHaveBeenCalled();
  });

  it('closes on "Nicx, tchau" without sending it to the model', async () => {
    mocks.stopRecording.mockResolvedValue('Nicx, tchau');
    render(<FloatingPage />);
    await waitFor(() => expect(mocks.onSilence).not.toBeNull());

    await act(async () => mocks.onSilence?.(true));

    await waitFor(() => expect(mocks.closeFloatingWindow).toHaveBeenCalled());
    expect(mocks.sendSpokenMessage).not.toHaveBeenCalled();
  });

  it('closes with the close button', async () => {
    render(<FloatingPage />);
    await waitFor(() => expect(mocks.startRecording).toHaveBeenCalled());

    await act(async () => screen.getByRole('button', { name: 'Fechar' }).click());

    expect(mocks.closeFloatingWindow).toHaveBeenCalled();
    expect(mocks.cancelRecording).toHaveBeenCalled();
  });

  it('pauses its own conversation while the dictation shortcut listens', async () => {
    const { rerender } = render(<FloatingPage />);
    await waitFor(() => expect(mocks.startRecording).toHaveBeenCalledTimes(1));

    mocks.dictation = 'ouvindo';
    rerender(<FloatingPage />);
    await waitFor(() => expect(screen.getByTestId('floating-status').textContent).toBe('Ditado: ouvindo…'));
    expect(mocks.cancelRecording).toHaveBeenCalled();

    mocks.dictation = 'transcrevendo';
    rerender(<FloatingPage />);
    await waitFor(() =>
      expect(screen.getByTestId('floating-status').textContent).toBe('Ditado: transcrevendo…'),
    );

    // Dictation over: the window stays open and listens again.
    mocks.dictation = 'pronto';
    rerender(<FloatingPage />);
    await waitFor(() => expect(mocks.startRecording).toHaveBeenCalledTimes(2));
    expect(mocks.closeFloatingWindow).not.toHaveBeenCalled();
  });
});
