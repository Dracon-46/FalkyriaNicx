/**
 * Assistentes (`/v1/assistentes`): o Nicx com nome, instruções e ferramentas
 * escolhidas pelo usuário. O ativo vale para o chat e a voz até voltar para o
 * Nicx. Tudo fica no PC.
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export interface AssistantInput {
  nome: string;
  instrucoes: string;
  descricao: string;
  /** Nomes das ferramentas; `["*"]` = todas; vazio = nenhuma (mais rápido). */
  ferramentas: string[];
  /** Usa e alimenta a memória do Nicx. */
  memoria: boolean;
  saudacao: string;
  /** Id do modelo pronto de onde saiu, se saiu de um. */
  modelo: string;
}

export interface Assistant extends AssistantInput {
  id: string;
  criado_em: string;
  atualizado_em: string;
}

export interface ToolInfo {
  nome: string;
  descricao: string;
}

export interface AssistantList {
  assistentes: Assistant[];
  ativo: string | null;
  prontos: Assistant[];
  ferramentas: ToolInfo[];
  limites: { nome: number; descricao: number; instrucoes: number; saudacao: number };
}

export const ALL_TOOLS = '*';

export function emptyAssistant(): AssistantInput {
  return { nome: '', instrucoes: '', descricao: '', ferramentas: [], memoria: true, saudacao: '', modelo: '' };
}

export function toInput(a: AssistantInput): AssistantInput {
  return {
    nome: a.nome,
    instrucoes: a.instrucoes,
    descricao: a.descricao,
    ferramentas: [...a.ferramentas],
    memoria: a.memoria,
    saudacao: a.saudacao,
    modelo: a.modelo,
  };
}

async function detail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

async function json<T>(res: Response, failure: string): Promise<T> {
  if (res.status === 404) {
    const why = await detail(res);
    throw new Error(i18n.t(why && why !== 'Not Found' ? 'assistentes.notFound' : 'assistentes.restartServer'));
  }
  if (res.status === 405) throw new Error(i18n.t('assistentes.restartServer'));
  if (res.status === 503) throw new Error(i18n.t('assistentes.noLocalModel'));
  if (res.status === 422) throw new Error(i18n.t('assistentes.nothingUsable'));
  if (res.status === 400) {
    const why = await detail(res);
    throw new Error(why ? i18n.t('assistentes.invalid', { detail: why }) : i18n.t(failure));
  }
  if (!res.ok) throw new Error(i18n.t(failure));
  return res.json() as Promise<T>;
}

function send(path: string, method: string, body?: unknown, signal?: AbortSignal): Promise<Response> {
  return apiFetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
}

const base = '/v1/assistentes';
const one = (id: string) => `${base}/${encodeURIComponent(id)}`;

export async function listarAssistentes(idioma?: string): Promise<AssistantList> {
  const query = idioma ? `?idioma=${encodeURIComponent(idioma)}` : '';
  return json(await apiFetch(`${base}${query}`), 'assistentes.loadFailed');
}

export async function criarAssistente(assistente: AssistantInput): Promise<Assistant> {
  return json(await send(base, 'POST', assistente), 'assistentes.saveFailed');
}

export async function atualizarAssistente(id: string, assistente: AssistantInput): Promise<Assistant> {
  return json(await send(one(id), 'PUT', assistente), 'assistentes.saveFailed');
}

export async function apagarAssistente(id: string): Promise<void> {
  await json(await send(one(id), 'DELETE'), 'assistentes.deleteFailed');
}

/** `null` volta para o Nicx de sempre. */
export async function ativarAssistente(id: string | null): Promise<string | null> {
  const res = await json<{ ativo: string | null }>(await send(`${base}/ativo`, 'PUT', { id }), 'assistentes.activateFailed');
  return res.ativo;
}

/** O modelo local monta um rascunho (30-90 s); nada é salvo. */
export async function proporAssistente(descricao: string, idioma?: string, signal?: AbortSignal): Promise<AssistantInput> {
  return json(await send(`${base}/propor`, 'POST', { descricao, idioma }, signal), 'assistentes.proposeFailed');
}
