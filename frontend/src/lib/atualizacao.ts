import { create } from 'zustand';
import { apiFetch } from './api';
import i18n from '../i18n';

/** Uma versão nas novidades (a mais nova primeiro). */
export interface Novidade {
  versao: string;
  data: string;
  titulo: string;
  itens: string[];
}

export interface EstadoAtualizacao {
  versao_atual: string;
  /** windows = NicxSetup.exe (atualiza pelo app); git = `nicx self-update`. */
  instalacao: 'windows' | 'git' | 'outro';
  pode_instalar: boolean;
  automatica: boolean;
  verificado_em: string | null;
  erro: string | null;
  ultima: { versao: string; publicado_em: string; tamanho: number | null; comando_mac: string } | null;
  ha_nova: boolean;
  baixando: boolean;
  progresso: number;
  erro_download: string | null;
  pronto_para_instalar: boolean;
  novidades: Novidade[];
  comando_git: string;
}

async function pedir(caminho: string, init: RequestInit = {}): Promise<EstadoAtualizacao> {
  const res = await apiFetch(`/v1/atualizacao${caminho}`, init);
  if (!res.ok) {
    let detalhe = String(res.status);
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === 'string') detalhe = j.detail;
    } catch {
      // sem JSON
    }
    throw new Error(i18n.t('atualizacoes.erro', { detail: detalhe }));
  }
  return res.json();
}

export const lerAtualizacao = () => pedir('');
export const procurarAtualizacao = () => pedir('/verificar', { method: 'POST' });
export const baixarAtualizacao = () => pedir('/baixar', { method: 'POST' });
export const instalarAtualizacao = async (): Promise<{ ok: boolean; versao: string }> => {
  const res = await apiFetch('/v1/atualizacao/instalar', { method: 'POST' });
  if (!res.ok) {
    const j = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(i18n.t('atualizacoes.erro', { detail: typeof j.detail === 'string' ? j.detail : res.status }));
  }
  return res.json();
};
export const configurarAtualizacao = (automatica: boolean) =>
  pedir('/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ automatica }),
  });

/** O último estado lido: o menu mostra um ponto quando há versão nova. */
export const useAtualizacao = create<{ estado: EstadoAtualizacao | null; definir: (e: EstadoAtualizacao | null) => void }>(
  (set) => ({ estado: null, definir: (estado) => set({ estado }) }),
);

/** Lê o estado (sem procurar de novo na internet); silencioso se o servidor for antigo. */
export async function atualizarEstado(): Promise<EstadoAtualizacao | null> {
  try {
    const estado = await lerAtualizacao();
    useAtualizacao.getState().definir(estado);
    return estado;
  } catch {
    return null;
  }
}

/**
 * Depois de mandar instalar: o servidor some enquanto o instalador troca os
 * arquivos e volta na versão nova. Espera a versão mudar e recarrega a página.
 */
export function esperarVersaoNova(
  versao: string,
  aoVoltar: () => void,
  aoDemorar: () => void,
  limiteMs = 20 * 60 * 1000,
): () => void {
  const inicio = Date.now();
  let parado = false;
  const tentar = async () => {
    if (parado) return;
    try {
      const estado = await lerAtualizacao();
      if (estado.versao_atual.startsWith(versao)) {
        aoVoltar();
        return;
      }
    } catch {
      // servidor fora do ar durante a troca: normal
    }
    if (Date.now() - inicio > limiteMs) {
      aoDemorar();
      return;
    }
    setTimeout(() => void tentar(), 3000);
  };
  setTimeout(() => void tentar(), 5000);
  return () => {
    parado = true;
  };
}
