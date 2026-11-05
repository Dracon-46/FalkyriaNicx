import * as vscode from 'vscode';

export const ESQUEMA = 'nicx-proposta';

interface Proposta {
  documento: vscode.Uri;
  versao: number;
  intervalo: vscode.Range;
  novoTrecho: string;
  textoProposto: string;
}

/**
 * A mudança que o Nicx propõe abre como diff (original × proposta) e só vai
 * para o arquivo quando a pessoa clica em Aplicar. Se o arquivo mudar no
 * meio, a proposta é descartada (o trecho já não é o mesmo).
 */
export class Propostas implements vscode.TextDocumentContentProvider, vscode.Disposable {
  private atual: Proposta | null = null;
  private readonly mudou = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this.mudou.event;
  private readonly assinaturas: vscode.Disposable[] = [];

  constructor() {
    this.assinaturas.push(
      vscode.workspace.onDidChangeTextDocument((e) => {
        if (this.atual && e.document.uri.toString() === this.atual.documento.toString() && e.contentChanges.length) {
          void this.descartar(vscode.l10n.t('O arquivo mudou; a proposta do Nicx foi descartada.'));
        }
      }),
    );
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    if (!this.atual || uri.query !== this.chave()) return '';
    return this.atual.textoProposto;
  }

  private chave(): string {
    return this.atual ? String(this.atual.versao) + ':' + this.atual.documento.toString() : '';
  }

  async mostrar(editor: vscode.TextEditor, intervalo: vscode.Range, novoTrecho: string): Promise<void> {
    const doc = editor.document;
    const inicio = doc.offsetAt(intervalo.start);
    const fim = doc.offsetAt(intervalo.end);
    const texto = doc.getText();
    this.atual = {
      documento: doc.uri,
      versao: doc.version,
      intervalo,
      novoTrecho,
      textoProposto: texto.slice(0, inicio) + novoTrecho + texto.slice(fim),
    };
    await vscode.commands.executeCommand('setContext', 'nicx.temProposta', true);
    const nome = doc.uri.path.split('/').pop() ?? 'arquivo';
    const direita = vscode.Uri.from({ scheme: ESQUEMA, path: doc.uri.path, query: this.chave() });
    this.mudou.fire(direita);
    await vscode.commands.executeCommand('vscode.diff', doc.uri, direita, vscode.l10n.t('Nicx: proposta para {0}', nome), {
      preview: true,
    });
    const escolha = await vscode.window.showInformationMessage(
      vscode.l10n.t('Aplicar a mudança que o Nicx propôs em {0}?', nome),
      vscode.l10n.t('Aplicar'),
      vscode.l10n.t('Descartar'),
    );
    if (escolha === vscode.l10n.t('Aplicar')) await this.aplicar();
    else if (escolha === vscode.l10n.t('Descartar')) await this.descartar();
  }

  async aplicar(): Promise<void> {
    const p = this.atual;
    if (!p) return;
    const doc = await vscode.workspace.openTextDocument(p.documento);
    if (doc.version !== p.versao) {
      await this.descartar(vscode.l10n.t('O arquivo mudou; peça a mudança de novo.'));
      return;
    }
    const edicao = new vscode.WorkspaceEdit();
    edicao.replace(p.documento, p.intervalo, p.novoTrecho);
    this.atual = null;
    await vscode.commands.executeCommand('setContext', 'nicx.temProposta', false);
    await fecharDiff();
    const ok = await vscode.workspace.applyEdit(edicao);
    if (ok) {
      const editor = await vscode.window.showTextDocument(doc, { preview: false });
      const fim = doc.positionAt(doc.offsetAt(p.intervalo.start) + p.novoTrecho.length);
      editor.selection = new vscode.Selection(p.intervalo.start, fim);
      vscode.window.setStatusBarMessage(vscode.l10n.t('Nicx: mudança aplicada (Ctrl+Z desfaz).'), 5000);
    } else {
      void vscode.window.showErrorMessage(vscode.l10n.t('Não consegui aplicar a mudança.'));
    }
  }

  async descartar(aviso?: string): Promise<void> {
    if (!this.atual) return;
    this.atual = null;
    await vscode.commands.executeCommand('setContext', 'nicx.temProposta', false);
    await fecharDiff();
    if (aviso) vscode.window.setStatusBarMessage(aviso, 5000);
  }

  dispose(): void {
    this.assinaturas.forEach((a) => a.dispose());
    this.mudou.dispose();
  }
}

async function fecharDiff(): Promise<void> {
  for (const grupo of vscode.window.tabGroups.all) {
    for (const aba of grupo.tabs) {
      const entrada = aba.input;
      if (entrada instanceof vscode.TabInputTextDiff && entrada.modified.scheme === ESQUEMA) {
        await vscode.window.tabGroups.close(aba);
      }
    }
  }
}
