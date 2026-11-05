import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CloudUpload, Download, KeyRound, Loader2, LogIn, LogOut, RotateCcw, ShieldCheck, Trash2, UserPlus } from 'lucide-react';
import {
  AccountError,
  aceitar,
  apagarBackup,
  apagarConta,
  baixarDados,
  cadastrar,
  confirmar,
  contaEstado,
  entrar,
  esqueci,
  exportarDados,
  fazerBackup,
  listarBackups,
  mudarNome,
  previaBackup,
  redefinir,
  reenviar,
  restaurarBackup,
  sair,
  type AccountState,
  type Backup,
  type BackupSummary,
} from '../../lib/conta';
import type { LegalDocument } from '../../lib/analytics';
import { LegalDocumentDialog } from '../Privacy/LegalDocumentDialog';

const input = { background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)' } as const;
const field = 'mt-1 w-full px-3 py-1.5 rounded-lg text-sm';
const label = 'block text-xs';
const buttonClass =
  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default';
const secondary = { background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' } as const;
const primary = { background: 'var(--color-accent)', color: 'white', border: '1px solid transparent' } as const;
const danger = { ...secondary, color: 'var(--color-error)', borderColor: 'var(--color-error)' } as const;

type Mode = 'entrar' | 'criar' | 'confirmar' | 'esqueci' | 'redefinir';

function errorText(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}

function formatDate(iso: string, lang: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(lang, { dateStyle: 'short', timeStyle: 'short' });
}

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** "Li e aceito os Termos de Uso e a Política de Privacidade", com os links. */
function Consent({ checked, onChange, onOpen }: { checked: boolean; onChange: (v: boolean) => void; onOpen: (d: LegalDocument) => void }) {
  const { t } = useTranslation();
  const link = (doc: LegalDocument, text: string) => (
    <button type="button" onClick={() => onOpen(doc)} className="underline cursor-pointer" style={{ color: 'var(--color-accent)', background: 'none', border: 'none', padding: 0 }}>
      {text}
    </button>
  );
  return (
    <label className="flex items-start gap-2 text-xs" style={{ color: 'var(--color-text)' }}>
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} data-testid="account-consent" />
      <span>
        {t('conta.consent.before')} {link('termos', t('conta.consent.terms'))} {t('conta.consent.and')} {link('privacidade', t('conta.consent.policy'))}.
      </span>
    </label>
  );
}

function LoggedOut({ onDone, onOpenDoc }: { onDone: (s: AccountState) => void; onOpenDoc: (d: LegalDocument) => void }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<Mode>('entrar');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(errorText(e, t('conta.genericError')));
    } finally {
      setBusy(false);
    }
  };

  const go = (next: Mode) => {
    setMode(next);
    setError('');
    setNotice('');
    setCode('');
  };

  const submit = () =>
    run(async () => {
      if (mode === 'entrar') return onDone(await entrar(email, password));
      if (mode === 'criar') {
        if (!agreed) throw new AccountError(t('conta.consent.required'));
        const r = await cadastrar(email, password, name, true);
        if (!r.confirmar) return onDone(await contaEstado());
        go('confirmar');
        return setNotice(t('conta.confirmSent', { email }));
      }
      if (mode === 'confirmar') return onDone(await confirmar(email, code));
      if (mode === 'esqueci') {
        await esqueci(email);
        go('redefinir');
        return setNotice(t('conta.recoverySent', { email }));
      }
      return onDone(await redefinir(email, code, password));
    });

  const needsPassword = mode === 'entrar' || mode === 'criar' || mode === 'redefinir';
  const needsCode = mode === 'confirmar' || mode === 'redefinir';
  const submitLabel = { entrar: 'conta.signIn', criar: 'conta.create', confirmar: 'conta.confirm', esqueci: 'conta.sendCode', redefinir: 'conta.savePassword' }[mode];

  return (
    // <form>: Enter no campo envia (entrar, criar, confirmar…).
    <form
      className="space-y-3"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!busy && email.trim()) void submit();
      }}
    >
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {t('conta.intro')}
      </p>
      <div className="flex flex-wrap gap-1.5" role="tablist">
        {(['entrar', 'criar'] as const).map((m) => (
          <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => go(m)} className={buttonClass} style={mode === m ? primary : secondary} data-testid={`account-tab-${m}`}>
            {m === 'entrar' ? <LogIn size={12} /> : <UserPlus size={12} />} {t(m === 'entrar' ? 'conta.signIn' : 'conta.create')}
          </button>
        ))}
      </div>
      {mode === 'criar' && (
        <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
          {t('conta.name')}
          <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} className={field} style={input} autoComplete="name" data-testid="account-name" />
        </label>
      )}
      <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
        {t('conta.email')}
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={mode === 'confirmar' || mode === 'redefinir'} className={field} style={input} autoComplete="email" data-testid="account-email" />
      </label>
      {needsCode && (
        <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
          {t('conta.code')}
          <input value={code} inputMode="numeric" maxLength={12} onChange={(e) => setCode(e.target.value.replace(/\s/g, ''))} className={`${field} font-mono tracking-widest`} style={input} autoComplete="one-time-code" data-testid="account-code" />
        </label>
      )}
      {needsPassword && (
        <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
          {t(mode === 'redefinir' ? 'conta.newPassword' : 'conta.password')}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={field} style={input} autoComplete={mode === 'entrar' ? 'current-password' : 'new-password'} data-testid="account-password" />
          {mode !== 'entrar' && (
            <span className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('conta.passwordHint')}
            </span>
          )}
        </label>
      )}
      {mode === 'criar' && <Consent checked={agreed} onChange={setAgreed} onOpen={onOpenDoc} />}
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" disabled={busy || !email.trim()} className={buttonClass} style={primary} data-testid="account-submit">
          {busy && <Loader2 size={12} className="animate-spin" />} {t(submitLabel)}
        </button>
        {mode === 'entrar' && (
          <button type="button" onClick={() => go('esqueci')} className="text-xs underline cursor-pointer" style={{ color: 'var(--color-text-secondary)', background: 'none', border: 'none' }} data-testid="account-forgot">
            {t('conta.forgot')}
          </button>
        )}
        {mode === 'confirmar' && (
          <>
            <button type="button" onClick={() => void run(async () => onDone(await entrar(email, password)))} disabled={busy} className={buttonClass} style={secondary} data-testid="account-confirmed">
              {t('conta.alreadyConfirmed')}
            </button>
            <button type="button" onClick={() => void run(async () => { await reenviar(email); setNotice(t('conta.confirmSent', { email })); })} disabled={busy} className={buttonClass} style={secondary}>
              {t('conta.resend')}
            </button>
          </>
        )}
        {(mode === 'esqueci' || mode === 'redefinir' || mode === 'confirmar') && (
          <button type="button" onClick={() => go('entrar')} className="text-xs underline cursor-pointer" style={{ color: 'var(--color-text-secondary)', background: 'none', border: 'none' }}>
            {t('conta.back')}
          </button>
        )}
      </div>
      {notice && (
        <p className="text-xs" role="status" style={{ color: 'var(--color-success)' }}>
          {notice}
        </p>
      )}
      {error && (
        <p className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </form>
  );
}

function Backups({ onSessionEnded }: { onSessionEnded: () => void }) {
  const { t, i18n } = useTranslation();
  const [list, setList] = useState<Backup[]>([]);
  const [secret, setSecret] = useState('');
  const [labelText, setLabelText] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [restoring, setRestoring] = useState<{ id: string; summary: BackupSummary | null } | null>(null);
  const [restoreSecret, setRestoreSecret] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const handle = useCallback(
    (e: unknown) => {
      if (e instanceof AccountError && e.sessionEnded) onSessionEnded();
      setError(errorText(e, t('conta.genericError')));
    },
    [onSessionEnded, t],
  );

  const load = useCallback(async () => {
    try {
      setList(await listarBackups());
    } catch (e) {
      handle(e);
    }
  }, [handle]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      handle(e);
    } finally {
      setBusy(null);
    }
  };

  const summaryText = (s: BackupSummary) => t('conta.backup.summary', { a: s.assistentes, r: s.rotinas, h: s.habilidades, m: s.mcp });

  return (
    <div className="space-y-3" data-testid="account-backups">
      <h4 className="text-xs font-semibold flex items-center gap-1.5" style={{ color: 'var(--color-text)' }}>
        <CloudUpload size={13} /> {t('conta.backup.title')}
      </h4>
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {t('conta.backup.intro')}
      </p>
      <p className="text-[11px] flex items-start gap-1" style={{ color: 'var(--color-warning)' }}>
        <KeyRound size={11} className="mt-0.5 shrink-0" /> {t('conta.backup.warning')}
      </p>
      <div className="grid sm:grid-cols-2 gap-2">
        <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
          {t('conta.backup.secret')}
          <input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} className={field} style={input} autoComplete="new-password" data-testid="backup-secret" />
        </label>
        <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
          {t('conta.backup.label')}
          <input value={labelText} maxLength={60} onChange={(e) => setLabelText(e.target.value)} placeholder={t('conta.backup.labelPlaceholder')} className={field} style={input} data-testid="backup-label" />
        </label>
      </div>
      <button
        type="button"
        onClick={() =>
          void run('new', async () => {
            const made = await fazerBackup(secret, labelText);
            setNotice(t('conta.backup.done', { summary: summaryText(made.resumo) }));
            setSecret('');
            setLabelText('');
            await load();
          })
        }
        disabled={busy !== null || secret.length < 8}
        className={buttonClass}
        style={primary}
        data-testid="backup-create"
      >
        {busy === 'new' ? <Loader2 size={12} className="animate-spin" /> : <CloudUpload size={12} />} {t('conta.backup.create')}
      </button>
      {notice && (
        <p className="text-xs" role="status" style={{ color: 'var(--color-success)' }}>
          {notice}
        </p>
      )}
      {error && (
        <p className="text-xs whitespace-pre-line" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
      {list.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {t('conta.backup.empty')}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {list.map((b) => (
            <li key={b.id} className="rounded-lg p-2.5 text-xs" style={{ border: '1px solid var(--color-border)' }} data-testid={`backup-${b.id}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span style={{ color: 'var(--color-text)' }}>
                  {b.rotulo} <span style={{ color: 'var(--color-text-tertiary)' }}>· {formatDate(b.criado_em, i18n.language)} · {formatSize(b.tamanho)}</span>
                </span>
                <span className="flex gap-1.5">
                  <button type="button" onClick={() => { setRestoring({ id: b.id, summary: null }); setRestoreSecret(''); }} className={buttonClass} style={secondary} data-testid={`backup-restore-${b.id}`}>
                    <RotateCcw size={12} /> {t('conta.backup.restore')}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirmDelete !== b.id) return setConfirmDelete(b.id);
                      setConfirmDelete(null);
                      void run(b.id, async () => {
                        await apagarBackup(b.id);
                        await load();
                      });
                    }}
                    className={buttonClass}
                    style={confirmDelete === b.id ? danger : secondary}
                    data-testid={`backup-delete-${b.id}`}
                  >
                    <Trash2 size={12} /> {t(confirmDelete === b.id ? 'conta.confirmShort' : 'conta.delete')}
                  </button>
                </span>
              </div>
              {restoring?.id === b.id && (
                <div className="mt-2 space-y-2">
                  <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
                    {t('conta.backup.secret')}
                    <input type="password" value={restoreSecret} onChange={(e) => setRestoreSecret(e.target.value)} className={field} style={input} data-testid="backup-restore-secret" />
                  </label>
                  {restoring.summary && (
                    <p style={{ color: 'var(--color-text-secondary)' }} data-testid="backup-summary">
                      {t('conta.backup.willRestore', { summary: summaryText(restoring.summary) })}
                    </p>
                  )}
                  <div className="flex gap-1.5">
                    {!restoring.summary ? (
                      <button type="button" onClick={() => void run(b.id, async () => setRestoring({ id: b.id, summary: await previaBackup(b.id, restoreSecret) }))} disabled={busy !== null || !restoreSecret} className={buttonClass} style={primary} data-testid="backup-open">
                        {busy === b.id && <Loader2 size={12} className="animate-spin" />} {t('conta.backup.open')}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() =>
                          void run(b.id, async () => {
                            const r = await restaurarBackup(b.id, restoreSecret);
                            setRestoring(null);
                            setNotice(t('conta.backup.restored'));
                            if (r.pulados.length) setError(t('conta.backup.skipped', { list: r.pulados.join('\n') }));
                          })
                        }
                        disabled={busy !== null}
                        className={buttonClass}
                        style={primary}
                        data-testid="backup-apply"
                      >
                        {busy === b.id && <Loader2 size={12} className="animate-spin" />} {t('conta.backup.apply')}
                      </button>
                    )}
                    <button type="button" onClick={() => setRestoring(null)} className={buttonClass} style={secondary}>
                      {t('conta.cancel')}
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LoggedIn({ state, onChange, onOpenDoc }: { state: AccountState; onChange: (s: AccountState | null) => void; onOpenDoc: (d: LegalDocument) => void }) {
  const { t, i18n } = useTranslation();
  const [name, setName] = useState(state.nome ?? '');
  const [agreed, setAgreed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const run = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      if (e instanceof AccountError && e.sessionEnded) return onChange(null);
      setError(errorText(e, t('conta.genericError')));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm" style={{ color: 'var(--color-text)' }} data-testid="account-email-shown">
          {state.email}
          {state.criado_em && (
            <span className="block text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
              {t('conta.since', { date: formatDate(state.criado_em, i18n.language) })}
            </span>
          )}
        </div>
        <button type="button" onClick={() => void run('out', async () => { await sair(); onChange(null); })} className={buttonClass} style={secondary} data-testid="account-signout">
          <LogOut size={12} /> {t('conta.signOut')}
        </button>
      </div>
      {state.protegido && (
        <p className="text-[11px] flex items-center gap-1" style={{ color: 'var(--color-text-tertiary)' }}>
          <ShieldCheck size={11} /> {t('conta.protected')}
        </p>
      )}

      {state.precisa_aceitar ? (
        <div className="rounded-lg p-3 space-y-2" style={{ border: '1px solid var(--color-warning)' }} data-testid="account-needs-consent">
          <p className="text-xs" style={{ color: 'var(--color-text)' }}>
            {t('conta.consent.update')}
          </p>
          <Consent checked={agreed} onChange={setAgreed} onOpen={onOpenDoc} />
          <button type="button" onClick={() => void run('accept', async () => onChange(await aceitar(state)))} disabled={!agreed || busy !== null} className={buttonClass} style={primary} data-testid="account-accept">
            {t('conta.consent.accept')}
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-end gap-2">
            <label className={`${label} flex-1`} style={{ color: 'var(--color-text-secondary)' }}>
              {t('conta.name')}
              <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} className={field} style={input} data-testid="account-name-edit" />
            </label>
            <button type="button" onClick={() => void run('name', async () => { onChange(await mudarNome(name)); setNotice(t('conta.saved')); })} disabled={busy !== null || name === (state.nome ?? '')} className={buttonClass} style={secondary}>
              {t('conta.save')}
            </button>
          </div>
          <Backups onSessionEnded={() => onChange(null)} />
        </>
      )}

      <div className="space-y-2 pt-2" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
        <h4 className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
          {t('conta.data.title')}
        </h4>
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {t('conta.data.intro')}
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void run('export', async () => baixarDados(await exportarDados()))} disabled={busy !== null} className={buttonClass} style={secondary} data-testid="account-export">
            <Download size={12} /> {t('conta.data.export')}
          </button>
          <button type="button" onClick={() => setDeleting((d) => !d)} className={buttonClass} style={danger} data-testid="account-delete">
            <Trash2 size={12} /> {t('conta.data.delete')}
          </button>
        </div>
        {deleting && (
          <div className="rounded-lg p-3 space-y-2" style={{ border: '1px solid var(--color-error)' }}>
            <p className="text-xs" style={{ color: 'var(--color-text)' }}>
              {t('conta.data.deleteWarning')}
            </p>
            <label className={label} style={{ color: 'var(--color-text-secondary)' }}>
              {t('conta.password')}
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={field} style={input} autoComplete="current-password" data-testid="account-delete-password" />
            </label>
            <button type="button" onClick={() => void run('delete', async () => { await apagarConta(password); onChange(null); })} disabled={!password || busy !== null} className={buttonClass} style={{ ...primary, background: 'var(--color-error)' }} data-testid="account-delete-confirm">
              {busy === 'delete' && <Loader2 size={12} className="animate-spin" />} {t('conta.data.deleteConfirm')}
            </button>
          </div>
        )}
      </div>
      {notice && (
        <p className="text-xs" role="status" style={{ color: 'var(--color-success)' }}>
          {notice}
        </p>
      )}
      {error && (
        <p className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </div>
  );
}

/** Configurações → Conta Falkyria (opcional). */
export function AccountSettings() {
  const { t } = useTranslation();
  const [state, setState] = useState<AccountState | null>(null);
  const [error, setError] = useState('');
  const [doc, setDoc] = useState<LegalDocument | null>(null);

  const load = useCallback(async () => {
    try {
      setState(await contaEstado());
      setError('');
    } catch (e) {
      setError(errorText(e, t('conta.genericError')));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div data-testid="account-settings">
      {error && (
        <p className="text-xs mb-2" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
      {!state && !error && <Loader2 size={14} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />}
      {state && !state.conectado && <LoggedOut onDone={setState} onOpenDoc={setDoc} />}
      {state?.conectado && <LoggedIn key={state.email} state={state} onChange={(s) => (s ? setState(s) : void load())} onOpenDoc={setDoc} />}
      <LegalDocumentDialog document={doc} onClose={() => setDoc(null)} />
    </div>
  );
}
