/**
 * Projetos do usuário (`/v1/projetos`): estado, decisões, pendências e
 * pastas, guardados só no PC (`~/.nicx/projetos.json`).
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export interface ProjectSummary {
  id: string;
  nome: string;
  estado: string;
  objetivo: string;
  ultima_atividade: string;
  pendencias_abertas: number;
  arquivado: boolean;
}

export interface ProjectDecision {
  texto: string;
  data: string;
  /** "auto" = anotada pela memória automática a partir da conversa. */
  origem: string;
}

export interface ProjectTask {
  id: string;
  texto: string;
  feita: boolean;
  criada_em: string;
  feita_em: string;
  origem: string;
}

export interface Project {
  id: string;
  nome: string;
  objetivo: string;
  estado: string;
  pastas: string[];
  arquivos: string[];
  decisoes: ProjectDecision[];
  pendencias: ProjectTask[];
  proximos_passos: string[];
  criado_em: string;
  ultima_atividade: string;
  idioma: string;
  arquivado: boolean;
}

export interface ProjectList {
  projetos: ProjectSummary[];
  /** O projeto da janela em uso (pasta do VS Code, arquivo aberto). */
  atual: string | null;
}

export interface ProjectSignals {
  git: {
    pasta: string;
    branch: string;
    commits: { hash: string; data: string; assunto: string }[];
    alterados: string[];
    total_alterados: number;
  } | null;
  recentes: { caminho: string; modificado: number }[];
}

export type ProjectUpdate = Partial<
  Pick<Project, 'nome' | 'objetivo' | 'estado' | 'proximos_passos' | 'pastas' | 'arquivos' | 'arquivado'>
>;

async function json<T>(res: Response): Promise<T> {
  if (res.status === 404 && res.url.endsWith('/v1/projetos')) {
    throw new Error(i18n.t('projects.restartServer'));
  }
  if (res.status === 409) throw new Error(i18n.t('projects.exists'));
  if (!res.ok) throw new Error(i18n.t('projects.saveFailed'));
  return res.json() as Promise<T>;
}

function send(path: string, method: string, body?: unknown): Promise<Response> {
  return apiFetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

const base = '/v1/projetos';
const one = (id: string) => `${base}/${encodeURIComponent(id)}`;

export async function listProjects(archived = false): Promise<ProjectList> {
  return json(await apiFetch(archived ? `${base}?arquivados=true` : base));
}

export async function getProject(id: string): Promise<Project> {
  return json(await apiFetch(one(id)));
}

export async function createProject(nome: string, objetivo = '', pastas: string[] = []): Promise<Project> {
  return json(await send(base, 'POST', { nome, objetivo, pastas }));
}

export async function updateProject(id: string, update: ProjectUpdate): Promise<Project> {
  return json(await send(one(id), 'PATCH', update));
}

export async function deleteProject(id: string): Promise<void> {
  await json(await send(one(id), 'DELETE'));
}

export async function addDecision(id: string, texto: string): Promise<Project> {
  return json(await send(`${one(id)}/decisoes`, 'POST', { texto }));
}

export async function addTask(id: string, texto: string): Promise<Project> {
  return json(await send(`${one(id)}/pendencias`, 'POST', { texto }));
}

export async function setTaskDone(id: string, taskId: string, feita: boolean): Promise<Project> {
  return json(await send(`${one(id)}/pendencias/${encodeURIComponent(taskId)}`, 'PATCH', { feita }));
}

export async function deleteTask(id: string, taskId: string): Promise<Project> {
  return json(await send(`${one(id)}/pendencias/${encodeURIComponent(taskId)}`, 'DELETE'));
}

export async function fetchProjectSignals(id: string): Promise<ProjectSignals> {
  return json(await apiFetch(`${one(id)}/sinais`));
}
