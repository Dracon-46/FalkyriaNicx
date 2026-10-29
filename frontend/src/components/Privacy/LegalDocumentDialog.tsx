import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchLegalDocument, type LegalDocument } from '../../lib/analytics';
import { splitTitle } from './legal-text';
import { Modal, buttonClass, buttonStyle } from './Modal';

// The Markdown renderer loads on first use, keeping Settings light to import.
const LegalMarkdown = lazy(() => import('./LegalMarkdown').then((m) => ({ default: m.LegalMarkdown })));

// An empty title or message means "use the translated fallback" (privacy.legal.*).
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
        setState({ kind: 'ready', title, body });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          kind: 'error',
          message: error instanceof Error ? error.message : '',
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
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-2 py-2" role="status" aria-label={t('privacy.legal.loading')}>
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
  const { t } = useTranslation();
  const { state, retry } = useLegalDocument(name, open);
  const fallbackTitle = t(`privacy.legal.titles.${name}`);
  const title = state.kind === 'ready' ? state.title || fallbackTitle : fallbackTitle;

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
          {t('privacy.legal.close')}
        </button>
      }
    >
      {state.kind === 'loading' && <LegalLoading />}
      {state.kind === 'error' && (
        <div role="alert" className="text-sm py-2" style={{ color: 'var(--color-text-secondary)' }}>
          <p className="mb-3">{state.message || t('privacy.legal.loadFailed')}</p>
          <button type="button" onClick={retry} className={buttonClass()} style={buttonStyle('neutral')}>
            {t('privacy.legal.retry')}
          </button>
        </div>
      )}
      {state.kind === 'ready' && <LegalText>{state.body}</LegalText>}
    </Modal>
  );
}
