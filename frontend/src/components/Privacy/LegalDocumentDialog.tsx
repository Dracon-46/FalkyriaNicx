import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import { fetchLegalDocument, type LegalDocument } from '../../lib/analytics';
import { splitTitle } from './legal-text';
import { Modal, buttonClass, buttonStyle } from './Modal';

// The Markdown renderer loads on first use, keeping Settings light to import.
const LegalMarkdown = lazy(() => import('./LegalMarkdown').then((m) => ({ default: m.LegalMarkdown })));

const FALLBACK_TITLES: Record<LegalDocument, string> = {
  privacidade: 'Política de privacidade',
  termos: 'Termos de uso',
  consentimento: 'Estatísticas anônimas de uso',
};

type DocState =
  | { kind: 'loading' }
  | { kind: 'ready'; title: string; body: string }
  | { kind: 'error'; message: string };

/** Hook: load one legal document's Markdown while `enabled`. */
export function useLegalDocument(name: LegalDocument, enabled = true) {
  const [state, setState] = useState<DocState>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setState({ kind: 'loading' });
    fetchLegalDocument(name)
      .then((text) => {
        if (cancelled) return;
        const { title, body } = splitTitle(text);
        setState({ kind: 'ready', title: title || FALLBACK_TITLES[name], body });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          kind: 'error',
          message: error instanceof Error ? error.message : 'Não foi possível carregar o documento.',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [name, enabled, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, retry };
}

export function LegalLoading() {
  return (
    <div className="flex flex-col gap-2 py-2" role="status" aria-label="Carregando o texto">
      {[92, 100, 84, 96, 60].map((w, i) => (
        <span
          key={i}
          className="data-skeleton block h-3 rounded"
          style={{ width: `${w}%`, background: 'var(--color-bg-tertiary)' }}
        />
      ))}
    </div>
  );
}

/** Legal Markdown, with the loading skeleton while the renderer loads. */
export function LegalText({ children }: { children: string }) {
  return (
    <Suspense fallback={<LegalLoading />}>
      <LegalMarkdown>{children}</LegalMarkdown>
    </Suspense>
  );
}

/** A readable modal with the privacy policy or the terms of use. */
export function LegalDocumentDialog({
  document,
  onClose,
}: {
  document: LegalDocument | null;
  onClose: () => void;
}) {
  const open = document !== null;
  const name = document ?? 'privacidade';
  const { state, retry } = useLegalDocument(name, open);
  const title = state.kind === 'ready' ? state.title : FALLBACK_TITLES[name];

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={title}
      size="lg"
      footer={
        <button type="button" onClick={onClose} className={buttonClass()} style={buttonStyle('neutral')}>
          Fechar
        </button>
      }
    >
      {state.kind === 'loading' && <LegalLoading />}
      {state.kind === 'error' && (
        <div role="alert" className="text-sm py-2" style={{ color: 'var(--color-text-secondary)' }}>
          <p className="mb-3">{state.message}</p>
          <button type="button" onClick={retry} className={buttonClass()} style={buttonStyle('neutral')}>
            Tentar de novo
          </button>
        </div>
      )}
      {state.kind === 'ready' && <LegalText>{state.body}</LegalText>}
    </Modal>
  );
}
