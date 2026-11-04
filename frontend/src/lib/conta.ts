/**
 * Conta Falkyria (`/v1/conta`), opcional. O login passa pelo servidor local do
 * Nicx (a sessão fica protegida no PC); o backup é cifrado no PC com uma senha
 * que nem a Falkyria conhece.
 */
import { apiFetch } from './api';
import i18n from '../i18n';

export interface AccountState {
  conectado: boolean;
  protegido: boolean;
  termos_versao: string;
  politica_versao: string;
  email?: string;
  nome?: string;
  aceitou_em?: string | null;
  criado_em?: string | null;
  precisa_aceitar?: boolean;
  erro?: string;
}

export interface Backup {
  id: string;
  rotulo: string;
  versao_nicx: string;
  tamanho: number;
  criado_em: string;
}

export interface BackupSummary {
  assistentes: number;
  rotinas: number;
  habilidades: number;
  mcp: number;
  pacotes_instalados: number;
}

export class AccountError extends Error {
  constructor(
    message: string,
    readonly sessionEnded = false,
  ) {
    super(message);
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

async function json<T>(res: Response): Promise<T> {
  if (res.status === 404 || res.status === 405) throw new AccountError(i18n.t('conta.restartServer'));
  if (!res.ok) {
    const why = await detail(res);
    throw new AccountError(why ? i18n.t('conta.failed', { detail: why }) : i18n.t('conta.genericError'), res.status === 401);
  }
  return res.json() as Promise<T>;
}

function send(path: string, method: string, body?: unknown): Promise<Response> {
  return apiFetch(`/v1/conta${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const contaEstado = async (): Promise<AccountState> => json(await apiFetch('/v1/conta'));
export const cadastrar = async (email: string, senha: string, nome: string, aceitou: boolean): Promise<{ confirmar: boolean }> =>
  json(await send('/cadastrar', 'POST', { email, senha, nome, aceitou }));
export const confirmar = async (email: string, codigo: string): Promise<AccountState> => json(await send('/confirmar', 'POST', { email, codigo }));
export const reenviar = async (email: string): Promise<void> => void (await json(await send('/reenviar', 'POST', { email })));
export const entrar = async (email: string, senha: string): Promise<AccountState> => json(await send('/entrar', 'POST', { email, senha }));
export const esqueci = async (email: string): Promise<void> => void (await json(await send('/esqueci', 'POST', { email })));
export const redefinir = async (email: string, codigo: string, senha: string): Promise<AccountState> =>
  json(await send('/redefinir', 'POST', { email, codigo, senha }));
export const sair = async (): Promise<void> => void (await json(await send('/sair', 'POST')));
export const aceitar = async (): Promise<AccountState> => json(await send('/aceitar', 'POST'));
export const mudarNome = async (nome: string): Promise<AccountState> => json(await send('/nome', 'PUT', { nome }));
export const listarBackups = async (): Promise<Backup[]> => (await json<{ backups: Backup[] }>(await send('/backups', 'GET'))).backups;
export const fazerBackup = async (senha: string, rotulo: string): Promise<Backup & { resumo: BackupSummary }> =>
  json(await send('/backups', 'POST', { senha, rotulo }));
export const previaBackup = async (id: string, senha: string): Promise<BackupSummary> =>
  json(await send(`/backups/${encodeURIComponent(id)}/previa`, 'POST', { senha }));
export const restaurarBackup = async (id: string, senha: string): Promise<{ pulados: string[] }> =>
  json(await send(`/backups/${encodeURIComponent(id)}/restaurar`, 'POST', { senha }));
export const apagarBackup = async (id: string): Promise<void> => void (await json(await send(`/backups/${encodeURIComponent(id)}`, 'DELETE')));
export const exportarDados = async (): Promise<Record<string, unknown>> => json(await send('/exportar', 'GET'));
export const apagarConta = async (senha: string): Promise<void> => void (await json(await send('/apagar', 'POST', { senha })));

/** Baixa os dados da conta (LGPD) como JSON. */
export function baixarDados(dados: Record<string, unknown>): void {
  const blob = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'conta-falkyria-meus-dados.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
