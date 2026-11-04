/**
 * Extensões (`/v1/extensoes`): servidores MCP, habilidades (SKILL.md) e
 * pacotes. Tudo fica no PC; token e variáveis de ambiente nunca voltam
 * inteiros (vêm como MASK).
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export const MASK = '••••••';

export type Trust = 'perguntar' | 'livre' | 'sempre';

export interface McpServerInput {
  nome: string;
  tipo: 'stdio' | 'http';
  comando: string;
  args: string[];
  env: Record<string, string>;
  url: string;
  token: string;
  incluir: string[];
  excluir: string[];
  ativo: boolean;
  confianca: Trust;
  descricao: string;
}

export interface McpServer extends McpServerInput {
  id: string;
  pacote: string;
  criado_em: string;
  situacao: { estado: 'ligado' | 'erro' | 'desligado'; ferramentas: string[]; erro?: string } | null;
}

export interface McpTemplate {
  chave: string;
  descricao: string;
  args: string[];
  env: string[];
  pede_args: string;
  confianca: Trust;
  comando: string;
}

export interface McpList {
  servidores: McpServer[];
  catalogo: McpTemplate[];
  npx: boolean;
}

export interface McpTest {
  ok: boolean;
  ferramentas: { nome: string; descricao: string }[];
  erro: string;
}

export interface Skill {
  nome: string;
  titulo: string;
  descricao: string;
  instrucoes: string;
  origem: string;
  ativa: boolean;
  editavel: boolean;
  versao: string;
  autor: string;
  perigosas: string[];
}

export interface SkillImport {
  nome: string;
  ok: boolean;
  pede_confirmacao?: boolean;
  perigosas?: string[];
  avisos?: string[];
}

export interface PackPermissions {
  comandos: string[];
  enderecos: string[];
  segredos: string[];
  ferramentas: string[];
  todas_as_ferramentas: boolean;
  rotinas_com_horario: string[];
}

export interface PackPreview {
  id: string;
  nome: string;
  descricao: string;
  versao: string;
  autor: string;
  pronto: boolean;
  itens: { assistentes: string[]; rotinas: string[]; habilidades: string[]; mcp: string[] };
  permissoes: PackPermissions;
  problemas: string[];
  instalado: boolean;
  versao_instalada: string;
}

export interface InstalledPack {
  id: string;
  nome: string;
  versao: string;
  autor: string;
  pronto: boolean;
  instalado_em: string;
  itens: Record<'assistentes' | 'rotinas' | 'habilidades' | 'mcp', string[]>;
}

export interface PackExport {
  id: string;
  nome: string;
  descricao: string;
  autor: string;
  versao: string;
  assistentes: string[];
  rotinas: string[];
  habilidades: string[];
  mcp: string[];
}

export function emptyServer(): McpServerInput {
  return {
    nome: '',
    tipo: 'stdio',
    comando: '',
    args: [],
    env: {},
    url: '',
    token: '',
    incluir: [],
    excluir: [],
    ativo: true,
    confianca: 'perguntar',
    descricao: '',
  };
}

export function serverInput(s: McpServerInput): McpServerInput {
  return {
    nome: s.nome,
    tipo: s.tipo,
    comando: s.comando,
    args: [...s.args],
    env: { ...s.env },
    url: s.url,
    token: s.token,
    incluir: [...s.incluir],
    excluir: [...s.excluir],
    ativo: s.ativo,
    confianca: s.confianca,
    descricao: s.descricao,
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
    throw new Error(why && why !== 'Not Found' ? why : i18n.t('extensoes.restartServer'));
  }
  if (res.status === 405) throw new Error(i18n.t('extensoes.restartServer'));
  if (res.status === 400 || res.status === 422) {
    const why = await detail(res);
    throw new Error(why ? i18n.t('extensoes.invalid', { detail: why }) : i18n.t(failure));
  }
  if (!res.ok) throw new Error(i18n.t(failure));
  return res.json() as Promise<T>;
}

function send(path: string, method: string, body?: unknown): Promise<Response> {
  return apiFetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

const base = '/v1/extensoes';
const enc = encodeURIComponent;

// ----------------------------------------------------------------- MCP
export async function listarMcp(): Promise<McpList> {
  return json(await apiFetch(`${base}/mcp`), 'extensoes.loadFailed');
}

export async function criarMcp(s: McpServerInput): Promise<McpServer> {
  return json(await send(`${base}/mcp`, 'POST', s), 'extensoes.saveFailed');
}

export async function atualizarMcp(id: string, s: McpServerInput): Promise<McpServer> {
  return json(await send(`${base}/mcp/${enc(id)}`, 'PUT', s), 'extensoes.saveFailed');
}

export async function apagarMcp(id: string): Promise<void> {
  await json(await send(`${base}/mcp/${enc(id)}`, 'DELETE'), 'extensoes.deleteFailed');
}

/** Liga, lista as ferramentas e desliga (até 90 s na primeira vez do npx). */
export async function testarMcp(s: McpServerInput, id?: string): Promise<McpTest> {
  return json(await send(`${base}/mcp/testar`, 'POST', { ...s, id }), 'extensoes.testFailed');
}

export async function recarregarMcp(): Promise<void> {
  await json(await send(`${base}/mcp/recarregar`, 'POST'), 'extensoes.reloadFailed');
}

// ----------------------------------------------------------- habilidades
export async function listarHabilidades(): Promise<{ habilidades: Skill[]; pasta: string }> {
  return json(await apiFetch(`${base}/habilidades`), 'extensoes.loadFailed');
}

export interface SkillInput {
  titulo: string;
  descricao: string;
  instrucoes: string;
}

export async function criarHabilidade(h: SkillInput): Promise<Skill> {
  return json(await send(`${base}/habilidades`, 'POST', h), 'extensoes.saveFailed');
}

export async function atualizarHabilidade(nome: string, h: SkillInput): Promise<Skill> {
  return json(await send(`${base}/habilidades/${enc(nome)}`, 'PUT', h), 'extensoes.saveFailed');
}

export async function ligarHabilidade(nome: string, ativa: boolean): Promise<void> {
  await json(await send(`${base}/habilidades/${enc(nome)}/ativa`, 'PUT', { ativa }), 'extensoes.saveFailed');
}

export async function apagarHabilidade(nome: string): Promise<void> {
  await json(await send(`${base}/habilidades/${enc(nome)}`, 'DELETE'), 'extensoes.deleteFailed');
}

export async function importarHabilidadesZip(arquivo: File, confirmar: boolean): Promise<SkillImport[]> {
  const form = new FormData();
  form.append('arquivo', arquivo);
  form.append('confirmar', confirmar ? 'true' : 'false');
  const res = await apiFetch(`${base}/habilidades/importar`, { method: 'POST', body: form });
  return (await json<{ resultados: SkillImport[] }>(res, 'extensoes.importFailed')).resultados;
}

export async function instalarHabilidadesGithub(url: string, confirmar: boolean): Promise<SkillImport[]> {
  const res = await send(`${base}/habilidades/github`, 'POST', { url, confirmar });
  return (await json<{ resultados: SkillImport[] }>(res, 'extensoes.importFailed')).resultados;
}

export async function recarregarHabilidades(): Promise<void> {
  await json(await send(`${base}/habilidades/recarregar`, 'POST'), 'extensoes.reloadFailed');
}

// ----------------------------------------------------------------- pacotes
export async function listarPacotes(idioma?: string): Promise<{ prontos: PackPreview[]; instalados: InstalledPack[] }> {
  const query = idioma ? `?idioma=${enc(idioma)}` : '';
  return json(await apiFetch(`${base}/pacotes${query}`), 'extensoes.loadFailed');
}

export async function previaPacote(conteudo: string): Promise<PackPreview> {
  return json(await send(`${base}/pacotes/previa`, 'POST', { conteudo }), 'extensoes.previewFailed');
}

export async function instalarPacote(pedido: {
  pronto?: string;
  conteudo?: string;
  com_mcp?: boolean;
  idioma?: string;
}): Promise<{ instalado: InstalledPack; pulados: string[] }> {
  return json(await send(`${base}/pacotes/instalar`, 'POST', pedido), 'extensoes.installFailed');
}

export async function desinstalarPacote(id: string): Promise<void> {
  await json(await send(`${base}/pacotes/${enc(id)}`, 'DELETE'), 'extensoes.deleteFailed');
}

export async function exportarPacote(pedido: PackExport): Promise<Record<string, unknown>> {
  return json(await send(`${base}/pacotes/exportar`, 'POST', pedido), 'extensoes.exportFailed');
}

/** Baixa o pacote como `<id>.nicx.json`. */
export function baixarPacote(pacote: Record<string, unknown>): void {
  const blob = new Blob([JSON.stringify(pacote, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${String(pacote.id || 'pacote')}.nicx.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
