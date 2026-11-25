/**
 * Caixa de entrada de decisões (`/v1/caixa`): aprovações dos agentes,
 * perguntas e planos do modo Trabalho, tarefas concluídas ou com erro.
 * Um só consultor alimenta o sininho e o humor de fundo do mascote.
 */
import { create } from 'zustand';
import { apiFetch } from './api';

export type InboxKind =
  | 'aprovacao'
  | 'trabalho_pergunta'
  | 'trabalho_plano'
  | 'trabalho_concluida'
  | 'trabalho_erro'
  | 'trabalho_interrompida'
  | 'agente_erro'
  | 'agente_atencao'
  | 'agente_orcamento';

export interface InboxItem {
  id: string;
  tipo: InboxKind;
  categoria: 'decisao' | 'aviso';
  /** ISO com fuso, ou "". */
  quando: string;
  titulo: string;
  texto: string;
  /** Id na origem (ação, tarefa ou agente). */
  ref: string;
  /** Página do app para ver mais. */
  link: string;
  extra: Record<string, unknown>;
}

export interface InboxActivity {
  trabalhando: boolean;
  esperando: number;
  ultimo_concluido: string;
  ultimo_erro: string;
}

export interface Inbox {
  decisoes: InboxItem[];
  avisos: InboxItem[];
  atividade: InboxActivity;
}

export async function obterCaixa(): Promise<Inbox> {
  const res = await apiFetch('/v1/caixa');
  if (!res.ok) throw new Error(String(res.status));
  return res.json() as Promise<Inbox>;
}

export async function dispensarAvisos(ids: string[] | 'todos'): Promise<void> {
  const body = ids === 'todos' ? { todos: true } : { ids };
  const res = await apiFetch('/v1/caixa/dispensar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(String(res.status));
}

interface InboxState {
  caixa: Inbox | null;
  /** Atualiza agora (depois de uma ação) sem esperar a próxima consulta. */
  atualizar: () => Promise<void>;
  /** Tira itens da tela na hora (a resposta do servidor confirma depois). */
  remover: (ids: string[]) => void;
}

export const useCaixa = create<InboxState>((set, get) => ({
  caixa: null,
  atualizar: async () => {
    try {
      set({ caixa: await obterCaixa() });
    } catch {
      // servidor fora do ar ou antigo: mantém o que havia
    }
  },
  remover: (ids) => {
    const atual = get().caixa;
    if (!atual) return;
    const fora = new Set(ids);
    set({
      caixa: {
        ...atual,
        decisoes: atual.decisoes.filter((i) => !fora.has(i.id)),
        avisos: atual.avisos.filter((i) => !fora.has(i.id)),
      },
    });
  },
}));

/** Rápido enquanto algo trabalha; devagar quando está tudo parado. */
export const POLL_ATIVO_MS = 4000;
export const POLL_PARADO_MS = 15000;

/** Começa a consultar a caixa; devolve a função que para. */
export function iniciarCaixa(): () => void {
  let parado = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const ciclo = async () => {
    await useCaixa.getState().atualizar();
    if (parado) return;
    const atv = useCaixa.getState().caixa?.atividade;
    timer = setTimeout(ciclo, atv?.trabalhando || atv?.esperando ? POLL_ATIVO_MS : POLL_PARADO_MS);
  };
  void ciclo();
  const aoFocar = () => void useCaixa.getState().atualizar();
  window.addEventListener('focus', aoFocar);
  return () => {
    parado = true;
    if (timer) clearTimeout(timer);
    window.removeEventListener('focus', aoFocar);
  };
}
