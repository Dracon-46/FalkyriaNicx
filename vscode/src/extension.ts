import * as vscode from 'vscode';
import { ChatNicx } from './chat';
import { ClienteNicx } from './cliente';
import { ACOES_COM_PROPOSTA, ajustarRecuo, extrairCodigo, MAX_CODIGO, pedido, type Acao, type Trecho } from './nucleo';
import { ESQUEMA, Propostas } from './proposta';

/**
 * Nicx para VS Code: chat ao lado do código e ações sobre o trecho
 * selecionado, usando o Nicx que roda neste PC (nada sai dele).
 */
export function activate(contexto: vscode.ExtensionContext): void {
  const cliente = new ClienteNicx();
  const chat = new ChatNicx(contexto.extensionUri, cliente);
  const propostas = new Propostas();

  contexto.subscriptions.push(
    propostas,
    vscode.window.registerWebviewViewProvider(ChatNicx.id, chat, { webviewOptions: { retainContextWhenHidden: true } }),
    vscode.workspace.registerTextDocumentContentProvider(ESQUEMA, propostas),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('nicx')) cliente.esquecerModelo();
    }),
    vscode.commands.registerCommand('nicx.abrirChat', () => vscode.commands.executeCommand(`${ChatNicx.id}.focus`)),
    vscode.commands.registerCommand('nicx.aplicar', () => propostas.aplicar()),
    vscode.commands.registerCommand('nicx.descartar', () => propostas.descartar()),
    ...(['explicar', 'corrigir', 'melhorar', 'testes', 'perguntar'] as const).map((acao) =>
      vscode.commands.registerCommand(`nicx.${acao}`, () => executar(acao, chat, cliente, propostas)),
    ),
  );
}

export function deactivate(): void {
  // nada a liberar além das assinaturas
}

function trechoDo(editor: vscode.TextEditor): { trecho: Trecho; intervalo: vscode.Range } | null {
  const doc = editor.document;
  let intervalo: vscode.Range = editor.selection;
  if (editor.selection.isEmpty) {
    // Sem seleção: o arquivo inteiro, se couber.
    if (doc.getText().length > MAX_CODIGO) return null;
    intervalo = new vscode.Range(doc.positionAt(0), doc.positionAt(doc.getText().length));
  } else {
    // Linhas inteiras: o recuo e a linha cortada no meio confundem o modelo.
    intervalo = new vscode.Range(intervalo.start.line, 0, intervalo.end.character === 0 && intervalo.end.line > intervalo.start.line ? intervalo.end.line : intervalo.end.line + 1, 0);
    intervalo = doc.validateRange(intervalo);
  }
  const linhas = vscode.workspace.getConfiguration('nicx').get<number>('linhasDeContexto', 40);
  const antesInicio = Math.max(0, intervalo.start.line - linhas);
  const depoisFim = Math.min(doc.lineCount, intervalo.end.line + linhas);
  const antes = doc.getText(new vscode.Range(antesInicio, 0, intervalo.start.line, 0));
  const depois = doc.getText(doc.validateRange(new vscode.Range(intervalo.end, new vscode.Position(depoisFim, 0))));
  const problemas = vscode.languages
    .getDiagnostics(doc.uri)
    .filter((d) => d.severity <= vscode.DiagnosticSeverity.Warning && d.range.intersection(intervalo))
    .map((d) => `linha ${d.range.start.line + 1}: ${d.message}`);
  return {
    intervalo,
    trecho: {
      arquivo: vscode.workspace.asRelativePath(doc.uri),
      linguagem: doc.languageId,
      codigo: doc.getText(intervalo),
      antes: antes.trim() ? antes : undefined,
      depois: depois.trim() ? depois : undefined,
      problemas,
      linhaInicial: intervalo.start.line + 1,
    },
  };
}

async function executar(acao: Acao, chat: ChatNicx, cliente: ClienteNicx, propostas: Propostas): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    if (acao === 'perguntar') await vscode.commands.executeCommand(`${ChatNicx.id}.focus`);
    else void vscode.window.showWarningMessage(vscode.l10n.t('Abra um arquivo e selecione um trecho.'));
    return;
  }
  const achado = trechoDo(editor);
  if (!achado) {
    void vscode.window.showWarningMessage(vscode.l10n.t('O arquivo é grande demais: selecione o trecho que interessa.'));
    return;
  }
  const { trecho, intervalo } = achado;
  const onde = `${trecho.arquivo}:${trecho.linhaInicial}`;

  if (acao === 'perguntar') {
    const pergunta = await vscode.window.showInputBox({
      prompt: vscode.l10n.t('Pergunte ao Nicx sobre {0}', onde),
      placeHolder: vscode.l10n.t('Ex.: por que isso dá erro?'),
    });
    if (!pergunta) return;
    await chat.perguntar(`${pergunta}\n(${onde})`, pedido('perguntar', trecho, pergunta));
    return;
  }

  if (!ACOES_COM_PROPOSTA.has(acao)) {
    const rotulos: Record<string, string> = {
      explicar: vscode.l10n.t('Explique {0}', onde),
      testes: vscode.l10n.t('Escreva testes para {0}', onde),
    };
    await chat.perguntar(rotulos[acao], pedido(acao, trecho));
    return;
  }

  // Corrigir / melhorar: a resposta vira uma proposta em diff.
  const titulo = acao === 'corrigir' ? vscode.l10n.t('Nicx corrigindo {0}…', onde) : vscode.l10n.t('Nicx melhorando {0}…', onde);
  const resposta = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: titulo, cancellable: true },
    async (_progresso, cancelar) => {
      const parar = new AbortController();
      cancelar.onCancellationRequested(() => parar.abort());
      let texto = '';
      try {
        for await (const parte of cliente.conversar([{ role: 'user', content: pedido(acao, trecho) }], parar.signal)) texto += parte;
      } catch (e) {
        if ((e as Error).name === 'AbortError') return null;
        void vscode.window.showErrorMessage((e as Error).message);
        return null;
      }
      return texto;
    },
  );
  if (resposta === null) return;
  const codigo = extrairCodigo(resposta);
  if (codigo === null) {
    // Sem bloco de código: mostra a resposta no chat.
    await chat.perguntar(acao === 'corrigir' ? vscode.l10n.t('Corrija {0}', onde) : vscode.l10n.t('Melhore {0}', onde), pedido(acao, trecho));
    return;
  }
  let novo = ajustarRecuo(trecho.codigo, codigo);
  if (trecho.codigo.endsWith('\n') && !novo.endsWith('\n')) novo += '\n';
  if (novo === trecho.codigo) {
    void vscode.window.showInformationMessage(vscode.l10n.t('O Nicx não achou nada para mudar em {0}.', onde));
    return;
  }
  await propostas.mostrar(editor, intervalo, novo);
}
