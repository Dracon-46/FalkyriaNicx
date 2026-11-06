import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X } from 'lucide-react';
import { basicSetup } from 'codemirror';
import { Compartment, EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { MergeView } from '@codemirror/merge';
import { LanguageDescription } from '@codemirror/language';
import { languages } from '@codemirror/language-data';
import { oneDark } from '@codemirror/theme-one-dark';

interface Props {
  nome: string;
  original: string;
  proposta: string;
  explicacao: string;
  onAplicar: () => void;
  onDescartar: () => void;
}

/** Original × proposta do Nicx, lado a lado; nada muda sem Aplicar. */
export function PropostaDiff({ nome, original, proposta, explicacao, onAplicar, onDescartar }: Props) {
  const { t } = useTranslation();
  const alvo = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!alvo.current) return;
    const escuro = document.documentElement.classList.contains('dark') ||
      (!document.documentElement.classList.contains('light') && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
    const linguaA = new Compartment();
    const linguaB = new Compartment();
    const comum = [basicSetup, EditorView.editable.of(false), EditorState.readOnly.of(true), escuro ? oneDark : []];
    const merge = new MergeView({
      parent: alvo.current,
      a: { doc: original, extensions: [...comum, linguaA.of([])] },
      b: { doc: proposta, extensions: [...comum, linguaB.of([])] },
      highlightChanges: true,
      gutter: true,
    });
    let vivo = true;
    const desc = LanguageDescription.matchFilename(languages, nome);
    if (desc) {
      void desc.load().then((suporte) => {
        if (!vivo) return;
        merge.a.dispatch({ effects: linguaA.reconfigure(suporte) });
        merge.b.dispatch({ effects: linguaB.reconfigure(suporte) });
      });
    }
    return () => {
      vivo = false;
      merge.destroy();
    };
  }, [nome, original, proposta]);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDescartar();
    };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onDescartar]);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.45)' }} role="dialog" aria-modal="true" aria-label={t('editor.proposta.titulo')} data-testid="editor-proposta">
      <div className="w-full max-w-5xl max-h-[90vh] flex flex-col rounded-xl overflow-hidden" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div className="px-4 py-3 flex items-center justify-between gap-3" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {t('editor.proposta.titulo')} · {nome}
            </h2>
            <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('editor.proposta.lados')}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <button type="button" onClick={onDescartar} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer" style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }} data-testid="editor-descartar">
              <X size={13} /> {t('editor.proposta.descartar')}
            </button>
            <button type="button" onClick={onAplicar} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer" style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent, white)' }} data-testid="editor-aplicar" autoFocus>
              <Check size={13} /> {t('editor.proposta.aplicar')}
            </button>
          </div>
        </div>
        <div ref={alvo} className="flex-1 min-h-0 overflow-auto text-[13px]" />
        {explicacao && (
          <p className="px-4 py-2 text-xs whitespace-pre-wrap" style={{ color: 'var(--color-text-secondary)', borderTop: '1px solid var(--color-border)' }}>
            {explicacao}
          </p>
        )}
      </div>
    </div>
  );
}
