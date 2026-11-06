import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { basicSetup, EditorView } from 'codemirror';
import { Compartment, EditorState } from '@codemirror/state';
import { keymap } from '@codemirror/view';
import { indentWithTab } from '@codemirror/commands';
import { LanguageDescription } from '@codemirror/language';
import { languages } from '@codemirror/language-data';
import { oneDark } from '@codemirror/theme-one-dark';

export interface Selecao {
  de: number;
  ate: number;
  texto: string;
  linhaInicial: number;
  linhaFinal: number;
}

export interface EditorApi {
  selecao(): Selecao;
  /** Linhas inteiras da seleção (ou o arquivo todo, sem seleção). */
  selecaoEmLinhas(): Selecao;
  texto(): string;
  trocar(de: number, ate: number, novo: string): void;
  inserir(texto: string): void;
  focar(): void;
}

interface Props {
  nome: string;
  texto: string;
  onChange: (texto: string) => void;
  onSalvar: () => void;
}

function escuro(): boolean {
  const raiz = document.documentElement;
  if (raiz.classList.contains('dark')) return true;
  if (raiz.classList.contains('light')) return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

const base = EditorView.theme({
  '&': { height: '100%', fontSize: '13px' },
  '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace' },
});

/** Editor de código (CodeMirror 6): Ctrl+S salva, Tab recua. */
export const CodeEditor = forwardRef<EditorApi, Props>(function CodeEditor({ nome, texto, onChange, onSalvar }, ref) {
  const alvo = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const linguagem = useRef(new Compartment());
  const tema = useRef(new Compartment());
  const callbacks = useRef({ onChange, onSalvar });
  callbacks.current = { onChange, onSalvar };

  // Cria o editor uma vez por arquivo aberto (o `nome` muda ao trocar).
  useEffect(() => {
    if (!alvo.current) return;
    const v = new EditorView({
      parent: alvo.current,
      state: EditorState.create({
        doc: texto,
        extensions: [
          basicSetup,
          keymap.of([
            indentWithTab,
            {
              key: 'Mod-s',
              preventDefault: true,
              run: () => {
                callbacks.current.onSalvar();
                return true;
              },
            },
          ]),
          base,
          linguagem.current.of([]),
          tema.current.of(escuro() ? oneDark : []),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) callbacks.current.onChange(u.state.doc.toString());
          }),
        ],
      }),
    });
    view.current = v;
    let vivo = true;
    const desc = LanguageDescription.matchFilename(languages, nome);
    if (desc) {
      void desc.load().then((suporte) => {
        if (vivo) v.dispatch({ effects: linguagem.current.reconfigure(suporte) });
      });
    }
    const observador = new MutationObserver(() => {
      v.dispatch({ effects: tema.current.reconfigure(escuro() ? oneDark : []) });
    });
    observador.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => {
      vivo = false;
      observador.disconnect();
      v.destroy();
      view.current = null;
    };
    // O texto inicial entra só na criação; depois o editor é a fonte.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nome]);

  useImperativeHandle(ref, () => ({
    selecao() {
      const v = view.current!;
      const { from, to } = v.state.selection.main;
      return {
        de: from,
        ate: to,
        texto: v.state.sliceDoc(from, to),
        linhaInicial: v.state.doc.lineAt(from).number,
        linhaFinal: v.state.doc.lineAt(to).number,
      };
    },
    selecaoEmLinhas() {
      const v = view.current!;
      const { from, to } = v.state.selection.main;
      const doc = v.state.doc;
      if (from === to) {
        return { de: 0, ate: doc.length, texto: doc.toString(), linhaInicial: 1, linhaFinal: doc.lines };
      }
      const primeira = doc.lineAt(from);
      // Seleção que termina no começo de uma linha não leva essa linha.
      const fimLinha = doc.lineAt(to);
      const ultima = to === fimLinha.from && to > from ? doc.line(Math.max(primeira.number, fimLinha.number - 1)) : fimLinha;
      const ate = Math.min(doc.length, ultima.to + (ultima.number < doc.lines ? 1 : 0));
      return { de: primeira.from, ate, texto: doc.sliceString(primeira.from, ate), linhaInicial: primeira.number, linhaFinal: ultima.number };
    },
    texto() {
      return view.current?.state.doc.toString() ?? '';
    },
    trocar(de, ate, novo) {
      const v = view.current;
      if (!v) return;
      v.dispatch({ changes: { from: de, to: ate, insert: novo }, selection: { anchor: de, head: de + novo.length } });
      v.focus();
    },
    inserir(trecho) {
      const v = view.current;
      if (!v) return;
      v.dispatch(v.state.replaceSelection(trecho));
      v.focus();
    },
    focar() {
      view.current?.focus();
    },
  }));

  return <div ref={alvo} className="h-full min-h-0 overflow-hidden" style={{ background: 'var(--color-surface)' }} data-testid="code-editor" />;
});
