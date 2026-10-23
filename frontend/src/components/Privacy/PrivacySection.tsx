import { useEffect, useState } from 'react';
import { FileText, ScrollText, ShieldCheck, Trash2 } from 'lucide-react';
import {
  forgetAnalyticsData,
  loadAnalyticsIdentity,
  setAnalyticsPreference,
  useAnalyticsIdentity,
  type LegalDocument,
} from '../../lib/analytics';
import { LegalDocumentDialog } from './LegalDocumentDialog';
import { ConfirmModal, buttonClass, buttonStyle } from './Modal';

/** "N eventos apagados dos servidores da Falkyria." in correct Portuguese. */
export function forgetMessage(removed: number): string {
  if (removed <= 0) return 'Nenhum evento desta instalação estava nos servidores da Falkyria.';
  const n = removed.toLocaleString('pt-BR');
  return removed === 1
    ? '1 evento apagado dos servidores da Falkyria.'
    : `${n} eventos apagados dos servidores da Falkyria.`;
}

type Notice = { tone: 'ok' | 'error'; text: string } | null;

/** Settings → Privacidade: consent toggle, legal texts and data deletion. */
export function PrivacySection() {
  const identity = useAnalyticsIdentity((s) => s.identity);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toggleError, setToggleError] = useState('');
  const [document, setDocument] = useState<LegalDocument | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [forgetting, setForgetting] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  useEffect(() => {
    let cancelled = false;
    loadAnalyticsIdentity({ force: true }).then((result) => {
      if (!cancelled) setLoadFailed(result === null);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const enabled = identity?.enabled === true;

  const toggle = async () => {
    if (!identity || saving) return;
    setSaving(true);
    setToggleError('');
    try {
      await setAnalyticsPreference(!enabled);
    } catch (e) {
      setToggleError(e instanceof Error ? e.message : 'Não foi possível salvar sua escolha.');
    } finally {
      setSaving(false);
    }
  };

  const forget = async () => {
    setForgetting(true);
    setNotice(null);
    try {
      const result = await forgetAnalyticsData();
      setNotice({ tone: 'ok', text: forgetMessage(result.removed) });
    } catch (e) {
      setNotice({
        tone: 'error',
        text: e instanceof Error ? e.message : 'Não foi possível apagar seus dados agora. Tente de novo.',
      });
    } finally {
      setForgetting(false);
      setConfirmOpen(false);
    }
  };

  return (
    <section
      aria-labelledby="privacy-heading"
      className="rounded-xl p-5"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <h3
        id="privacy-heading"
        className="flex items-center gap-2 text-sm font-semibold mb-2"
        style={{ color: 'var(--color-text)' }}
      >
        <ShieldCheck size={15} aria-hidden="true" style={{ color: 'var(--color-accent)' }} />
        Privacidade
      </h3>
      <p className="text-xs leading-relaxed mb-1" style={{ color: 'var(--color-text-secondary)' }}>
        Suas conversas, arquivos e memórias ficam no seu computador. Com a sua permissão, o
        Nicx envia à Falkyria apenas estatísticas anônimas de uso (recursos usados, tempos,
        tipos de erro), em servidores no Brasil, apagadas após 24 meses.
      </p>

      <div
        className="flex items-center justify-between gap-4 py-3"
        style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
      >
        <div className="min-w-0">
          <div id="privacy-toggle-label" className="text-sm" style={{ color: 'var(--color-text)' }}>
            Enviar estatísticas anônimas de uso
          </div>
          <div id="privacy-toggle-hint" className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
            {identity === null
              ? loadFailed
                ? 'Não foi possível ler sua escolha: o servidor do Nicx não respondeu.'
                : 'Verificando...'
              : enabled
                ? 'Ativado. Obrigado por ajudar a melhorar o Nicx.'
                : 'Desativado. Nada é enviado.'}
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-labelledby="privacy-toggle-label"
          aria-describedby="privacy-toggle-hint"
          disabled={!identity || saving}
          onClick={() => void toggle()}
          className="relative w-11 h-6 shrink-0 rounded-full transition-colors cursor-pointer disabled:cursor-default disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
          style={{ background: enabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary)' }}
        >
          <span
            aria-hidden="true"
            className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-transform bg-white motion-reduce:transition-none"
            style={{
              transform: enabled ? 'translateX(20px)' : 'translateX(0)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            }}
          />
        </button>
      </div>
      {toggleError && (
        <p role="alert" className="text-xs mt-2" style={{ color: 'var(--color-error)' }}>
          {toggleError}
        </p>
      )}

      <div
        className="flex flex-wrap items-center justify-between gap-3 py-3"
        style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
      >
        <div className="min-w-0">
          <div className="text-sm" style={{ color: 'var(--color-text)' }}>Documentos</div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
            {identity?.policy_version
              ? `Política de privacidade, versão ${identity.policy_version}`
              : 'Como a Falkyria trata os seus dados'}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDocument('privacidade')}
            className={buttonClass('sm')}
            style={buttonStyle('neutral')}
          >
            <FileText size={13} aria-hidden="true" /> Política de privacidade
          </button>
          <button
            type="button"
            onClick={() => setDocument('termos')}
            className={buttonClass('sm')}
            style={buttonStyle('neutral')}
          >
            <ScrollText size={13} aria-hidden="true" /> Termos de uso
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-3">
        <div className="min-w-0 max-w-sm">
          <div className="text-sm" style={{ color: 'var(--color-text)' }}>Apagar meus dados</div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
            Remove dos servidores da Falkyria os eventos enviados por esta instalação e gera um
            novo código anônimo.
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setNotice(null);
            setConfirmOpen(true);
          }}
          disabled={forgetting}
          className={buttonClass('sm')}
          style={{
            background: 'transparent',
            color: 'var(--color-error)',
            border: '1px solid var(--color-error)',
          }}
        >
          <Trash2 size={13} aria-hidden="true" /> Apagar meus dados
        </button>
      </div>
      {notice && (
        <p
          role={notice.tone === 'error' ? 'alert' : 'status'}
          className="text-xs mt-3 px-3 py-2 rounded-lg"
          style={{
            color: notice.tone === 'error' ? 'var(--color-error)' : 'var(--color-text)',
            background:
              notice.tone === 'error'
                ? 'color-mix(in srgb, var(--color-error) 8%, transparent)'
                : 'var(--color-accent-subtle)',
          }}
        >
          {notice.text}
        </p>
      )}

      <ConfirmModal
        open={confirmOpen}
        onOpenChange={(next) => {
          if (!forgetting) setConfirmOpen(next);
        }}
        title="Apagar seus dados de uso?"
        description={
          <>
            <p className="mb-2">
              Os eventos de uso que esta instalação enviou serão apagados dos servidores da
              Falkyria, e o Nicx passará a usar um novo código anônimo.
            </p>
            <p>
              Suas conversas não são afetadas: elas nunca saem do seu computador. Esta ação não
              pode ser desfeita.
            </p>
          </>
        }
        confirmLabel={forgetting ? 'Apagando...' : 'Apagar dados'}
        onConfirm={() => void forget()}
        busy={forgetting}
        destructive
      />
      <LegalDocumentDialog document={document} onClose={() => setDocument(null)} />
    </section>
  );
}
