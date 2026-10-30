import { useEffect, useState } from 'react';
import { DictationUnsupportedError, fetchDictationState } from './api';

/**
 * Ditado universal (`[ditado]`): o servidor ouve e digita sozinho; a janela
 * flutuante só acompanha o estado para mostrar "ouvindo" no mascote e
 * pausar a própria conversa por voz enquanto isso.
 */

export const DICTATION_POLL_MS = 1000;

/** O ditado está com o microfone aberto ou transcrevendo. */
export function isDictating(state: string | null | undefined): boolean {
  return state === 'ouvindo' || state === 'transcrevendo';
}

/**
 * Estado do ditado, perguntado a cada `intervalMs`. Para de perguntar se o
 * servidor não tem a rota (versão antiga); erros de rede só esperam mais.
 */
export function useDictationState(intervalMs = DICTATION_POLL_MS): string | null {
  const [state, setState] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = () =>
      fetchDictationState()
        .then((next) => {
          if (cancelled) return;
          setState(next);
          timer = setTimeout(poll, intervalMs);
        })
        .catch((e) => {
          if (cancelled || e instanceof DictationUnsupportedError) return;
          timer = setTimeout(poll, intervalMs * 5);
        });
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [intervalMs]);

  return state;
}
