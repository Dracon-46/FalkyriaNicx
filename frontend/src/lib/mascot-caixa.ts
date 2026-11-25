import { useCaixa, type InboxActivity } from './caixa';
import { useMascot, type AmbientMood } from './mascot';

type InboxState = ReturnType<typeof useCaixa.getState>;
type MascotState = ReturnType<typeof useMascot.getState>;

interface Store<T> {
  getState: () => T;
  subscribe: (listener: (state: T, prev: T) => void) => () => void;
}

/** Quanto tempo o mascote comemora uma tarefa concluída ou lamenta um erro. */
export const DONE_MS = 4000;
export const FAIL_MS = 5000;

/** O humor de fundo que vale enquanto nada novo acontece. */
export function steadyMood(atv: InboxActivity | undefined): AmbientMood {
  if (!atv) return 'idle';
  if (atv.esperando > 0) return 'waiting';
  if (atv.trabalhando) return 'working';
  return 'idle';
}

/**
 * Liga a caixa de entrada ao humor de fundo do mascote: `waiting` enquanto
 * alguma decisão espera a pessoa, `working` enquanto algo roda em segundo
 * plano, `happy` por um instante quando uma tarefa termina e `error` quando
 * algo falha. A primeira leitura só define o estado (não comemora o que já
 * tinha acontecido antes de abrir o app). Devolve a função que desliga.
 */
export function bindMascotToCaixa(
  caixa: Store<InboxState> = useCaixa,
  mascot: Store<MascotState> = useMascot,
): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let visto: InboxActivity | null = caixa.getState().caixa?.atividade ?? null;

  const steady = () => steadyMood(caixa.getState().caixa?.atividade);
  const apply = (mood: AmbientMood) => {
    if (mascot.getState().ambient !== mood) mascot.getState().setAmbient(mood);
  };
  const flash = (mood: AmbientMood, ms: number) => {
    if (timer) clearTimeout(timer);
    apply(mood);
    timer = setTimeout(() => {
      timer = null;
      apply(steady());
    }, ms);
  };

  if (visto) apply(steadyMood(visto));

  const unsubscribe = caixa.subscribe((state) => {
    const atv = state.caixa?.atividade;
    if (!atv) return;
    const antes = visto;
    visto = atv;
    if (antes && atv.ultimo_erro && atv.ultimo_erro > antes.ultimo_erro) {
      flash('error', FAIL_MS);
    } else if (antes && atv.ultimo_concluido && atv.ultimo_concluido > antes.ultimo_concluido) {
      flash('happy', DONE_MS);
    } else if (!timer) {
      apply(steadyMood(atv));
    }
  });

  return () => {
    unsubscribe();
    if (timer) clearTimeout(timer);
  };
}
