import * as vscode from 'vscode';
import type { ClienteNicx } from './cliente';
import type { Mensagem } from './nucleo';

/** Mensagens que o painel manda para a extensão. */
type DoPainel =
  | { tipo: 'pronto' }
  | { tipo: 'enviar'; texto: string }
  | { tipo: 'parar' }
  | { tipo: 'novo' }
  | { tipo: 'inserir'; codigo: string }
  | { tipo: 'copiar'; codigo: string };

const MAX_HISTORICO = 12;

/** O chat do Nicx na barra lateral do VS Code. */
export class ChatNicx implements vscode.WebviewViewProvider {
  static readonly id = 'nicx.chat';
  private view?: vscode.WebviewView;
  private historico: Mensagem[] = [];
  private parar?: AbortController;
  private pendentes: Array<{ visivel: string; paraModelo: string }> = [];
  private pronto = false;

  constructor(
    private readonly extensao: vscode.Uri,
    private readonly cliente: ClienteNicx,
  ) {}

  resolveWebviewView(view: vscode.WebviewView): void {
    this.view = view;
    this.pronto = false;
    view.webview.options = { enableScripts: true, localResourceRoots: [vscode.Uri.joinPath(this.extensao, 'media')] };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage((m: DoPainel) => void this.receber(m));
    view.onDidDispose(() => {
      this.view = undefined;
      this.pronto = false;
    });
  }

  /** Abre o painel e manda uma pergunta (com o trecho do editor). */
  async perguntar(visivel: string, paraModelo: string): Promise<void> {
    this.pendentes.push({ visivel, paraModelo });
    await vscode.commands.executeCommand(`${ChatNicx.id}.focus`);
    if (this.pronto) this.esvaziar();
  }

  private esvaziar(): void {
    const fila = this.pendentes.splice(0);
    for (const p of fila) void this.enviar(p.visivel, p.paraModelo);
  }

  private postar(m: Record<string, unknown>): void {
    void this.view?.webview.postMessage(m);
  }

  private async receber(m: DoPainel): Promise<void> {
    switch (m.tipo) {
      case 'pronto':
        this.pronto = true;
        this.esvaziar();
        break;
      case 'enviar':
        if (m.texto.trim()) await this.enviar(m.texto.trim(), m.texto.trim());
        break;
      case 'parar':
        this.parar?.abort();
        break;
      case 'novo':
        this.parar?.abort();
        this.historico = [];
        this.postar({ tipo: 'limpar' });
        break;
      case 'copiar':
        await vscode.env.clipboard.writeText(m.codigo);
        vscode.window.setStatusBarMessage(vscode.l10n.t('Nicx: código copiado.'), 3000);
        break;
      case 'inserir': {
        const editor = vscode.window.visibleTextEditors.find((e) => e.document.uri.scheme === 'file') ?? vscode.window.activeTextEditor;
        if (!editor) {
          void vscode.window.showWarningMessage(vscode.l10n.t('Abra um arquivo para inserir o código.'));
          break;
        }
        await editor.edit((e) => e.replace(editor.selection, m.codigo));
        break;
      }
    }
  }

  private async enviar(visivel: string, paraModelo: string): Promise<void> {
    this.parar?.abort();
    const parar = new AbortController();
    this.parar = parar;
    const id = Date.now().toString(36);
    this.postar({ tipo: 'usuario', texto: visivel });
    this.postar({ tipo: 'inicio', id });
    this.historico.push({ role: 'user', content: paraModelo });
    let resposta = '';
    try {
      for await (const parte of this.cliente.conversar(this.historico.slice(-MAX_HISTORICO), parar.signal)) {
        resposta += parte;
        this.postar({ tipo: 'parte', id, texto: parte });
      }
      this.historico.push({ role: 'assistant', content: resposta });
      this.postar({ tipo: 'fim', id });
    } catch (e) {
      // Pergunta sem resposta não fica no histórico (atrapalharia a próxima).
      this.historico.pop();
      if ((e as Error).name === 'AbortError') {
        if (resposta) this.historico.push({ role: 'user', content: paraModelo }, { role: 'assistant', content: resposta });
        this.postar({ tipo: 'fim', id, parado: true });
      } else {
        this.postar({ tipo: 'erro', id, texto: (e as Error).message });
      }
    } finally {
      if (this.parar === parar) this.parar = undefined;
    }
  }

  private html(webview: vscode.Webview): string {
    const nonce = Array.from({ length: 24 }, () => Math.floor(Math.random() * 36).toString(36)).join('');
    const script = webview.asWebviewUri(vscode.Uri.joinPath(this.extensao, 'media', 'chat.js'));
    const estilo = webview.asWebviewUri(vscode.Uri.joinPath(this.extensao, 'media', 'chat.css'));
    const t = {
      vazio: vscode.l10n.t('Pergunte sobre o seu código, ou selecione um trecho e use o menu Nicx (botão direito).'),
      placeholder: vscode.l10n.t('Pergunte ao Nicx…'),
      enviar: vscode.l10n.t('Enviar'),
      parar: vscode.l10n.t('Parar'),
      novo: vscode.l10n.t('Nova conversa'),
      copiar: vscode.l10n.t('Copiar'),
      inserir: vscode.l10n.t('Inserir no editor'),
      pensando: vscode.l10n.t('Pensando… (o modelo roda no seu PC)'),
      parado: vscode.l10n.t('(parado)'),
      voce: vscode.l10n.t('Você'),
    };
    return `<!DOCTYPE html>
<html lang="${vscode.env.language}">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="${estilo}">
<title>Nicx</title>
</head>
<body>
<div id="topo"><button id="novo" class="secundario" title="${t.novo}">${t.novo}</button></div>
<div id="conversa" aria-live="polite"><p class="vazio">${t.vazio}</p></div>
<form id="formulario">
<textarea id="campo" rows="3" placeholder="${t.placeholder}"></textarea>
<div class="botoes"><button type="submit" id="enviar">${t.enviar}</button><button type="button" id="parar" class="secundario" hidden>${t.parar}</button></div>
</form>
<script nonce="${nonce}">window.NICX_TEXTOS = ${JSON.stringify(t).replace(/</g, '\\u003c')};</script>
<script nonce="${nonce}" src="${script}"></script>
</body>
</html>`;
  }
}
