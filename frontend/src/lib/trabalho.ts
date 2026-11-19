/**
 * Modo Trabalho (`/v1/trabalho`): o Nicx trabalha numa pasta escolhida, com
 * plano aprovado pela pessoa, ferramentas presas à pasta e desfazer.
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export type TaskState =
  | 'planejando'
  | 'aguardando_aprovacao'
  | 'executando'
  | 'pausada'
  | 'aguardando_confirmacao'
  | 'concluida'
  | 'parada'
  | 'erro'
  | 'desfeita'
  | 'interrompida';

export type StepState = 'pendente' | 'fazendo' | 'feito' | 'falhou' | 'pulado';

export interface Step {
  descricao: string;
  estado: StepState;
  resultado: string;
}

export interface LogEntry {
  quando: string;
  tipo: string;
  texto: string;
}

export interface Task {
  id: string;
  pasta: string;
  pedido: string;
  estado: TaskState;
  plano: Step[];
  registro?: LogEntry[];
  pergunta: { texto: string } | null;
  resumo: string;
  erro: string;
  criado_em: string;
  atualizado_em: string;
  arquivos_mudados: string[];
  problemas?: string[];
}

/** Estados em que a tarefa ainda está trabalhando (vale acompanhar). */
export const ACTIVE_STATES: TaskState[] = ['planejando', 'executando', 'pausada', 'aguardando_confirmacao'];

/** Estados em que dá para (re)começar a execução. */
export const STARTABLE_STATES: TaskState[] = ['aguardando_aprovacao', 'parada', 'interrompida', 'erro'];

async function detail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

async function json<T>(res: Response, failure: string): Promise<T> {
  if (res.status === 404 || res.status === 405) throw new Error(i18n.t('trabalho.restartServer'));
  if (res.status === 409 || res.status === 422) {
    const why = await detail(res);
    throw new Error(why || i18n.t(failure));
  }
  if (!res.ok) throw new Error(i18n.t(failure));
  return res.json() as Promise<T>;
}

function post(path: string, body?: unknown): Promise<Response> {
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
}

const base = '/v1/trabalho';
const one = (id: string) => `${base}/${encodeURIComponent(id)}`;

/** Abre a janela de pastas do Windows; "" se a pessoa cancelou. */
export async function escolherPasta(): Promise<string> {
  const r = await json<{ pasta: string }>(await post(`${base}/escolher-pasta`), 'trabalho.pickFailed');
  return r.pasta;
}

export async function listarTarefas(): Promise<Task[]> {
  const r = await json<{ tarefas: Task[] }>(await apiFetch(base), 'trabalho.loadFailed');
  return r.tarefas;
}

export async function verTarefa(id: string): Promise<Task> {
  return json(await apiFetch(one(id)), 'trabalho.loadFailed');
}

export async function criarTarefa(pasta: string, pedido: string): Promise<Task> {
  return json(await post(base, { pasta, pedido }), 'trabalho.createFailed');
}

export async function aprovarTarefa(id: string, passos?: string[]): Promise<Task> {
  return json(await post(`${one(id)}/aprovar`, passos ? { passos } : {}), 'trabalho.actionFailed');
}

export async function acaoTarefa(id: string, acao: 'pausar' | 'continuar' | 'parar' | 'desfazer'): Promise<Task> {
  return json(await post(`${one(id)}/${acao}`), 'trabalho.actionFailed');
}

export async function responderTarefa(id: string, confirmado: boolean): Promise<Task> {
  return json(await post(`${one(id)}/responder`, { confirmado }), 'trabalho.actionFailed');
}
