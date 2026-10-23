import { useCallback, useEffect, useState } from 'react';
import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { Loader2, ShieldAlert } from 'lucide-react';
import { checkIsAdmin, getPainelClient, painelErrorMessage } from '../lib/painel';
import { PainelLogin } from '../components/Painel/PainelLogin';
import { PainelDashboard, SignOutButton } from '../components/Painel/PainelDashboard';
import '../components/Painel/painel.css';

type Access =
  | { kind: 'checking' }
  | { kind: 'admin' }
  | { kind: 'denied' }
  | { kind: 'error'; message: string };

type Connection =
  | { kind: 'connecting' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; client: SupabaseClient };

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex-1 flex items-center justify-center px-4 py-10">{children}</div>;
}

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="w-full max-w-md rounded-xl p-6 text-center"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <ShieldAlert size={22} aria-hidden="true" className="mx-auto mb-3" style={{ color: 'var(--color-accent)' }} />
      <h1 className="text-base font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
        {title}
      </h1>
      {children}
    </div>
  );
}

function Busy({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
      <Loader2 size={16} aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
      {label}
    </div>
  );
}

/**
 * "Painel Falkyria": anonymous usage analytics for Falkyria administrators.
 * Sign-in goes straight to Falkyria's Supabase project; the database only
 * returns data to accounts on the administrators' allowlist.
 */
export function PainelPage() {
  const [connection, setConnection] = useState<Connection>({ kind: 'connecting' });
  const [attempt, setAttempt] = useState(0);
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [access, setAccess] = useState<Access>({ kind: 'checking' });
  const [signingOut, setSigningOut] = useState(false);

  // Connect and follow the persisted session.
  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    setConnection({ kind: 'connecting' });
    getPainelClient()
      .then(async (client) => {
        if (cancelled) return;
        const { data } = client.auth.onAuthStateChange((_event, next) => {
          if (!cancelled) setSession(next);
        });
        unsubscribe = () => data.subscription.unsubscribe();
        const { data: current } = await client.auth.getSession();
        if (cancelled) return;
        setSession(current.session);
        setConnection({ kind: 'ready', client });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setConnection({
            kind: 'error',
            message: error instanceof Error ? error.message : 'Não foi possível abrir o painel.',
          });
        }
      });
    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [attempt]);

  const client = connection.kind === 'ready' ? connection.client : null;
  const userId = session?.user?.id;

  // Ask the database whether this account may read the analytics.
  useEffect(() => {
    if (!client || !userId) return;
    let cancelled = false;
    setAccess({ kind: 'checking' });
    checkIsAdmin(client)
      .then((isAdmin) => {
        if (!cancelled) setAccess({ kind: isAdmin ? 'admin' : 'denied' });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setAccess({ kind: 'error', message: error instanceof Error ? error.message : painelErrorMessage(error) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client, userId]);

  const signOut = useCallback(async () => {
    if (!client) return;
    setSigningOut(true);
    try {
      await client.auth.signOut();
    } finally {
      setSession(null);
      setSigningOut(false);
    }
  }, [client]);

  const denyAccess = useCallback(() => setAccess({ kind: 'denied' }), []);

  if (connection.kind === 'connecting' || (connection.kind === 'ready' && session === undefined)) {
    return (
      <Centered>
        <Busy label="Abrindo o painel..." />
      </Centered>
    );
  }

  if (connection.kind === 'error') {
    return (
      <Centered>
        <Notice title="Não foi possível abrir o painel">
          <p className="text-sm mb-4" style={{ color: 'var(--color-text-secondary)' }}>
            {connection.message}
          </p>
          <button
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
            className="text-sm underline underline-offset-2 cursor-pointer"
            style={{ color: 'var(--color-accent)' }}
          >
            Tentar de novo
          </button>
        </Notice>
      </Centered>
    );
  }

  if (!client) return null;

  if (!session) {
    return (
      <div className="painel flex-1 overflow-y-auto">
        <Centered>
          <PainelLogin client={client} />
        </Centered>
      </div>
    );
  }

  const email = session.user?.email ?? '';

  if (access.kind === 'checking') {
    return (
      <Centered>
        <Busy label="Verificando seu acesso..." />
      </Centered>
    );
  }

  if (access.kind === 'denied' || access.kind === 'error') {
    return (
      <Centered>
        <Notice title={access.kind === 'denied' ? 'Acesso não liberado' : 'Não foi possível verificar seu acesso'}>
          <p className="text-sm mb-1" style={{ color: 'var(--color-text-secondary)' }}>
            {access.kind === 'denied'
              ? 'Sua conta não tem acesso ao painel. Peça a um administrador da Falkyria.'
              : access.message}
          </p>
          {email && (
            <p className="text-xs mb-4" style={{ color: 'var(--color-text-tertiary)' }}>
              Conectado como {email}
            </p>
          )}
          <div className="flex justify-center">
            <SignOutButton onSignOut={() => void signOut()} busy={signingOut} />
          </div>
        </Notice>
      </Centered>
    );
  }

  return (
    <div className="painel flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-6xl mx-auto">
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              Painel Falkyria
            </h1>
            <p className="text-sm mt-1 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
              Uso anônimo do Nicx, enviado só por instalações que deram consentimento. Nenhuma
              conversa ou dado pessoal chega aqui.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {email && (
              <span className="text-xs truncate max-w-[14rem]" style={{ color: 'var(--color-text-tertiary)' }}>
                {email}
              </span>
            )}
            <SignOutButton onSignOut={() => void signOut()} busy={signingOut} />
          </div>
        </header>
        <PainelDashboard client={client} onAccessDenied={denyAccess} />
      </div>
    </div>
  );
}

export default PainelPage;
