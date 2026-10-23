import { useId, useState, type FormEvent } from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';
import { LogIn, MailCheck, UserPlus } from 'lucide-react';
import { painelErrorMessage } from '../../lib/painel';
import { NicxMascot } from '../Mascot/NicxMascot';

type Mode = 'entrar' | 'criar';

const MIN_PASSWORD = 10;

const inputClass =
  'w-full px-3 py-2 rounded-lg text-sm outline-none transition-colors ' +
  'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--color-accent)]';
const inputStyle = {
  background: 'var(--color-input-bg)',
  color: 'var(--color-text)',
  border: '1px solid var(--color-input-border)',
} as const;

/** Email + password sign-in for Falkyria administrators, with sign-up. */
export function PainelLogin({ client }: { client: SupabaseClient }) {
  const [mode, setMode] = useState<Mode>('entrar');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sentTo, setSentTo] = useState('');
  const emailId = useId();
  const passwordId = useId();
  const hintId = useId();

  const switchMode = (next: Mode) => {
    setMode(next);
    setError('');
    setSentTo('');
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    const address = email.trim();
    setError('');
    if (mode === 'criar' && password.length < MIN_PASSWORD) {
      setError(`A senha precisa ter pelo menos ${MIN_PASSWORD} caracteres.`);
      return;
    }
    setBusy(true);
    try {
      if (mode === 'entrar') {
        const { error: authError } = await client.auth.signInWithPassword({ email: address, password });
        if (authError) setError(painelErrorMessage(authError));
      } else {
        const { error: authError } = await client.auth.signUp({ email: address, password });
        if (authError) {
          setError(painelErrorMessage(authError));
        } else {
          setSentTo(address);
          setPassword('');
        }
      }
    } catch (e) {
      setError(painelErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto">
      <div className="flex flex-col items-center text-center mb-6">
        <NicxMascot size="md" decorative />
        <h1 className="text-lg font-semibold mt-2" style={{ color: 'var(--color-text)' }}>
          Painel Falkyria
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>
          Estatísticas anônimas de uso do Nicx. Acesso restrito à equipe da Falkyria.
        </p>
      </div>

      <div className="rounded-xl p-5" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--color-text)' }}>
          {mode === 'entrar' ? 'Entrar no painel' : 'Criar uma conta'}
        </h2>

        {sentTo ? (
          <div role="status" className="text-sm leading-relaxed" style={{ color: 'var(--color-text)' }}>
            <MailCheck size={20} aria-hidden="true" className="mb-2" style={{ color: 'var(--color-accent)' }} />
            <p className="mb-2">
              Conta criada. Enviamos um e-mail de confirmação para <strong>{sentTo}</strong>.
            </p>
            <p className="text-xs mb-4" style={{ color: 'var(--color-text-secondary)' }}>
              Abra o link do e-mail e depois volte aqui para entrar. Se não chegar em alguns
              minutos, confira a caixa de spam.
            </p>
            <button
              type="button"
              onClick={() => switchMode('entrar')}
              className="text-sm underline underline-offset-2 cursor-pointer"
              style={{ color: 'var(--color-accent)' }}
            >
              Voltar para o login
            </button>
          </div>
        ) : (
          <form onSubmit={(e) => void submit(e)} noValidate={false} className="flex flex-col gap-4">
            {mode === 'criar' && (
              <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                Depois de criar a conta, você vai receber um e-mail de confirmação. O acesso aos
                dados é liberado por um administrador da Falkyria.
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <label htmlFor={emailId} className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                E-mail
              </label>
              <input
                id={emailId}
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
                style={inputStyle}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={passwordId} className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                Senha
              </label>
              <input
                id={passwordId}
                type="password"
                autoComplete={mode === 'entrar' ? 'current-password' : 'new-password'}
                required
                minLength={mode === 'criar' ? MIN_PASSWORD : undefined}
                aria-describedby={mode === 'criar' ? hintId : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                style={inputStyle}
              />
              {mode === 'criar' && (
                <span id={hintId} className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  Pelo menos {MIN_PASSWORD} caracteres.
                </span>
              )}
            </div>
            {error && (
              <p role="alert" className="text-xs leading-relaxed" style={{ color: 'var(--color-error)' }}>
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 min-h-9 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-opacity disabled:opacity-60 disabled:cursor-default focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
              style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)' }}
            >
              {mode === 'entrar' ? <LogIn size={15} aria-hidden="true" /> : <UserPlus size={15} aria-hidden="true" />}
              {busy ? 'Aguarde...' : mode === 'entrar' ? 'Entrar' : 'Criar conta'}
            </button>
          </form>
        )}
      </div>

      {!sentTo && (
        <p className="text-xs text-center mt-4" style={{ color: 'var(--color-text-secondary)' }}>
          {mode === 'entrar' ? 'Ainda não tem conta?' : 'Já tem uma conta?'}{' '}
          <button
            type="button"
            onClick={() => switchMode(mode === 'entrar' ? 'criar' : 'entrar')}
            className="underline underline-offset-2 cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            style={{ color: 'var(--color-accent)' }}
          >
            {mode === 'entrar' ? 'Criar conta' : 'Voltar para o login'}
          </button>
        </p>
      )}
    </div>
  );
}
