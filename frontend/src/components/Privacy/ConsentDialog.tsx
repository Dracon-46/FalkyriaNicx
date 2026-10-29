import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NicxMascot } from '../Mascot/NicxMascot';
import {
  loadAnalyticsIdentity,
  setAnalyticsPreference,
  useAnalyticsIdentity,
} from '../../lib/analytics';
import { LegalDocumentDialog, LegalLoading, LegalText, useLegalDocument } from './LegalDocumentDialog';
import { Modal, buttonClass, buttonStyle } from './Modal';

type Choice = 'accept' | 'decline';

interface ConsentDialogProps {
  open: boolean;
  policyVersion?: string;
  /** Save the choice; rejects with a user-facing message. */
  onChoose: (enabled: boolean) => Promise<unknown>;
  /** Close without a saved choice (asked again on the next launch). */
  onDismiss: () => void;
}

/**
 * First-launch question: may Nicx send anonymous usage statistics?
 * Both answers carry the same weight, and Esc means "Agora não".
 */
export function ConsentDialog({ open, policyVersion, onChoose, onDismiss }: ConsentDialogProps) {
  const { t } = useTranslation();
  const { state } = useLegalDocument('consentimento', open);
  const [busy, setBusy] = useState<Choice | null>(null);
  const [error, setError] = useState('');
  const [policyOpen, setPolicyOpen] = useState(false);

  const choose = async (choice: Choice) => {
    if (busy) return;
    setBusy(choice);
    setError('');
    try {
      await onChoose(choice === 'accept');
    } catch (e) {
      if (choice === 'decline') {
        // Nothing is sent without consent anyway: close for now and ask
        // again next time instead of trapping the user here.
        onDismiss();
      } else {
        setError(e instanceof Error ? e.message : t('privacy.saveFailed'));
      }
    } finally {
      setBusy(null);
    }
  };

  // Fallbacks for while the server's consent text loads or cannot be read.
  const fallbackTitle = t('privacy.consent.fallbackTitle');
  const title = state.kind === 'ready' ? state.title || fallbackTitle : fallbackTitle;

  return (
    <Modal
      open={open}
      onOpenChange={(next, details) => {
        if (!next && details.reason === 'escape-key') {
          void choose('decline');
        }
      }}
      title={title}
      icon={<NicxMascot size="md" decorative className="shrink-0 -my-2" />}
      size="md"
      showClose={false}
      disablePointerDismissal
      focusDialog
      footer={
        <>
          <button
            type="button"
            onClick={() => void choose('decline')}
            disabled={busy !== null}
            aria-busy={busy === 'decline' || undefined}
            className={`${buttonClass()} sm:min-w-32`}
            style={buttonStyle('neutral')}
          >
            {t('privacy.consent.notNow')}
          </button>
          <button
            type="button"
            onClick={() => void choose('accept')}
            disabled={busy !== null}
            aria-busy={busy === 'accept' || undefined}
            className={`${buttonClass()} sm:min-w-32`}
            style={buttonStyle('neutral')}
          >
            {t('privacy.consent.accept')}
          </button>
        </>
      }
    >
      {state.kind === 'loading' && <LegalLoading />}
      {state.kind !== 'loading' && (
        <LegalText>{state.kind === 'ready' ? state.body : t('privacy.consent.fallbackText')}</LegalText>
      )}
      <p className="mt-4 text-sm">
        <button
          type="button"
          onClick={() => setPolicyOpen(true)}
          className="underline underline-offset-2 cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          style={{ color: 'var(--color-accent)' }}
        >
          {t('privacy.consent.readPolicy')}
        </button>
        {policyVersion && (
          <span className="ml-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('privacy.consent.version', { version: policyVersion })}
          </span>
        )}
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
      <LegalDocumentDialog
        document={policyOpen ? 'privacidade' : null}
        onClose={() => setPolicyOpen(false)}
      />
    </Modal>
  );
}

/**
 * Shows the consent dialog once, while the server reports that no choice
 * has been recorded yet. Retries quietly when the server is unreachable.
 */
export function ConsentGate() {
  const identity = useAnalyticsIdentity((s) => s.identity);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (identity) return;
    const load = () => {
      void loadAnalyticsIdentity();
    };
    load();
    window.addEventListener('focus', load);
    const interval = setInterval(load, 60_000);
    return () => {
      window.removeEventListener('focus', load);
      clearInterval(interval);
    };
  }, [identity]);

  const open = !!identity && !identity.choice_recorded && !dismissed;

  return (
    <ConsentDialog
      open={open}
      policyVersion={identity?.policy_version}
      onChoose={setAnalyticsPreference}
      onDismiss={() => setDismissed(true)}
    />
  );
}
