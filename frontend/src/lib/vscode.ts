import { apiFetch } from './api';
import i18n from '../i18n';

/** Extensão "Nicx para VS Code" (`/v1/vscode`). */
export interface EstadoVSCode {
  /** O VS Code está instalado neste PC. */
  vscode: boolean;
  /** A extensão veio junto com esta instalação do Nicx. */
  pacote: boolean;
  /** Versão da extensão instalada no VS Code, ou null. */
  instalada: string | null;
}

async function ler(res: Response): Promise<EstadoVSCode> {
  if (!res.ok) {
    let detalhe = String(res.status);
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === 'string') detalhe = j.detail;
    } catch {
      // sem JSON
    }
    throw new Error(i18n.t('settings.vscode.erro', { detail: detalhe }));
  }
  return res.json();
}

export const estadoVSCode = async () => ler(await apiFetch('/v1/vscode'));
export const instalarVSCode = async () => ler(await apiFetch('/v1/vscode/instalar', { method: 'POST' }));
