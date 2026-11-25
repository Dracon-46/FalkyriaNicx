import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { create } from 'zustand';
import type { Inbox, InboxActivity } from './caixa';
import { useMascot, visibleMood } from './mascot';
import { bindMascotToCaixa, DONE_MS, FAIL_MS, steadyMood } from './mascot-caixa';

function inbox(atv: Partial<InboxActivity>): Inbox {
  return {
    decisoes: [],
    avisos: [],
    atividade: { trabalhando: false, esperando: 0, ultimo_concluido: '', ultimo_erro: '', ...atv },
  };
}

function setup(inicial: Inbox | null = null) {
  const caixa = create<{ caixa: Inbox | null; atualizar: () => Promise<void>; remover: () => void }>(() => ({
    caixa: inicial,
    atualizar: async () => undefined,
    remover: () => undefined,
  }));
  const unbind = bindMascotToCaixa(caixa as unknown as Parameters<typeof bindMascotToCaixa>[0]);
  return { caixa, unbind, set: (c: Inbox) => caixa.setState({ caixa: c }) };
}

describe('bindMascotToCaixa', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useMascot.setState({ mood: 'idle', ambient: 'idle', level: 0 });
  });
  afterEach(() => vi.useRealTimers());

  it('trabalhando, esperando e de volta ao normal', () => {
    const { set, unbind } = setup();
    set(inbox({ trabalhando: true }));
    expect(useMascot.getState().ambient).toBe('working');
    set(inbox({ trabalhando: true, esperando: 1 }));
    expect(useMascot.getState().ambient).toBe('waiting');
    set(inbox({}));
    expect(useMascot.getState().ambient).toBe('idle');
    unbind();
  });

  it('comemora uma tarefa nova concluída e depois volta ao estado de fundo', () => {
    const { set, unbind } = setup(inbox({ trabalhando: true }));
    expect(useMascot.getState().ambient).toBe('working');
    set(inbox({ ultimo_concluido: '2026-11-25T12:00:00+00:00' }));
    expect(useMascot.getState().ambient).toBe('happy');
    vi.advanceTimersByTime(DONE_MS + 10);
    expect(useMascot.getState().ambient).toBe('idle');
    unbind();
  });

  it('erro novo deixa o mascote triste por um tempo', () => {
    const { set, unbind } = setup(inbox({}));
    set(inbox({ ultimo_erro: '2026-11-25T12:00:00+00:00', esperando: 1 }));
    expect(useMascot.getState().ambient).toBe('error');
    vi.advanceTimersByTime(FAIL_MS + 10);
    expect(useMascot.getState().ambient).toBe('waiting');
    unbind();
  });

  it('não comemora o que já estava concluído ao abrir o app', () => {
    const { set, unbind } = setup();
    set(inbox({ ultimo_concluido: '2026-11-20T10:00:00+00:00' }));
    expect(useMascot.getState().ambient).toBe('idle');
    unbind();
  });

  it('o humor da conversa tem prioridade sobre o de fundo', () => {
    useMascot.setState({ mood: 'thinking', ambient: 'working' });
    expect(visibleMood(useMascot.getState())).toBe('thinking');
    useMascot.setState({ mood: 'idle' });
    expect(visibleMood(useMascot.getState())).toBe('working');
    expect(steadyMood(undefined)).toBe('idle');
  });
});
