import * as vscode from 'vscode';
import { lerPartes, servidorLocal, SISTEMA, type Mensagem } from './nucleo';

/** Conversa com o servidor do Nicx deste PC (`nicx serve`, porta 8000 por padrão). */
export class ClienteNicx {
  private modeloPadrao: string | null = null;

  private config() {
    const c = vscode.workspace.getConfiguration('nicx');
    return {
      servidor: servidorLocal(c.get<string>('servidor', 'http://127.0.0.1:8000')),
      modelo: c.get<string>('modelo', '').trim(),
      chave: c.get<string>('chaveApi', '').trim(),
    };
  }

  private cabecalhos(chave: string, json = false): Record<string, string> {
    const h: Record<string, string> = {};
    if (json) h['Content-Type'] = 'application/json';
    if (chave) h.Authorization = `Bearer ${chave}`;
    return h;
  }

  /** O modelo escolhido nas configurações ou o padrão do servidor. */
  async modelo(signal?: AbortSignal): Promise<string> {
    const { servidor, modelo, chave } = this.config();
    if (modelo) return modelo;
    if (this.modeloPadrao) return this.modeloPadrao;
    const res = await this.pedir(new URL('/v1/info', servidor), { headers: this.cabecalhos(chave), signal });
    const info = (await res.json()) as { model?: unknown };
    if (typeof info.model !== 'string' || !info.model) throw new Error(vscode.l10n.t('O Nicx não informou o modelo. Escolha um em Configurações > Nicx > Modelo.'));
    this.modeloPadrao = info.model;
    return info.model;
  }

  esquecerModelo(): void {
    this.modeloPadrao = null;
  }

  /** A resposta do Nicx, pedaço por pedaço. */
  async *conversar(mensagens: Mensagem[], signal?: AbortSignal): AsyncGenerator<string> {
    const { servidor, chave } = this.config();
    const modelo = await this.modelo(signal);
    const res = await this.pedir(new URL('/v1/chat/completions', servidor), {
      method: 'POST',
      headers: this.cabecalhos(chave, true),
      body: JSON.stringify({
        model: modelo,
        stream: true,
        // Pedido do editor: direto ao modelo, sem ferramentas do PC, e o
        // código fica fora da memória automática do Nicx.
        editor: true,
        language: vscode.env.language,
        temperature: 0.2,
        max_tokens: 2048,
        messages: [{ role: 'system', content: SISTEMA }, ...mensagens],
      }),
      signal,
    });
    if (!res.body) throw new Error(vscode.l10n.t('O Nicx não respondeu.'));
    yield* lerPartes(res.body as unknown as AsyncIterable<Uint8Array>);
  }

  private async pedir(url: URL, init: RequestInit): Promise<Response> {
    let res: Response;
    try {
      res = await fetch(url, init);
    } catch (e) {
      if ((e as Error).name === 'AbortError') throw e;
      throw new Error(
        vscode.l10n.t('Não encontrei o Nicx em {0}. Abra o Nicx (menu Iniciar) e tente de novo.', url.origin),
      );
    }
    if (res.status === 401) throw new Error(vscode.l10n.t('O Nicx pediu a chave da API: preencha Configurações > Nicx > Chave da API.'));
    if (!res.ok) {
      let detalhe = '';
      try {
        const j = (await res.json()) as { detail?: unknown };
        if (typeof j.detail === 'string') detalhe = `: ${j.detail}`;
      } catch {
        // sem JSON
      }
      throw new Error(vscode.l10n.t('O Nicx respondeu com erro {0}{1}', String(res.status), detalhe));
    }
    return res;
  }
}
