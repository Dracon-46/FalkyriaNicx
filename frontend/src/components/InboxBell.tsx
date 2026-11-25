import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  Bell,
  Bot,
  Briefcase,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  ListChecks,
  X,
  XCircle,
} from 'lucide-react';
import i18n from '../i18n';
import { approveAction, denyAction } from '../lib/api';
import { dispensarAvisos, useCaixa, type InboxItem } from '../lib/caixa';
import { responderTarefa } from '../lib/trabalho';

const TIER_STYLES: Record<string, { color: string; bg: string }> = {
  trivial: { color: 'var(--color-text-secondary)', bg: 'color-mix(in srgb, var(--color-text-secondary) 10%, transparent)' },
  low: { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
  medium: { color: 'var(--color-warning)', bg: 'color-mix(in srgb, var(--color-warning) 12%, transparent)' },
  high: { color: 'var(--color-error)', bg: 'color-mix(in srgb, var(--color-error) 12%, transparent)' },
};

const yes = {
  background: 'color-mix(in srgb, var(--color-success) 12%, transparent)',
  color: 'var(--color-success)',
  border: '1px solid color-mix(in srgb, var(--color-success) 22%, transparent)',
} as const;
const no = {
  background: 'color-mix(in srgb, var(--color-error) 12%, transparent)',
  color: 'var(--color-error)',
  border: '1px solid color-mix(in srgb, var(--color-error) 22%, transparent)',
} as const;
const neutral = {
  background: 'var(--color-bg-tertiary)',
  color: 'var(--color-text)',
  border: '1px solid var(--color-border)',
} as const;
const actionClass =
  'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition-opacity cursor-pointer disabled:opacity-40';

function timeAgo(iso: string): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return '';
  const m = Math.floor(diff / 60000);
  if (m < 1) return i18n.t('nav.chats.justNow');
  const rtf = new Intl.RelativeTimeFormat(i18n.language, { numeric: 'auto', style: 'short' });
  if (m < 60) return rtf.format(-m, 'minute');
  const h = Math.floor(m / 60);
  if (h < 24) return rtf.format(-h, 'hour');
  return rtf.format(-Math.floor(h / 24), 'day');
}

function KindIcon({ item }: { item: InboxItem }) {
  const size = 13;
  if (item.tipo === 'trabalho_concluida') return <CheckCircle size={size} style={{ color: 'var(--color-success)' }} />;
  if (item.tipo.endsWith('_erro') || item.tipo === 'agente_orcamento')
    return <XCircle size={size} style={{ color: 'var(--color-error)' }} />;
  if (item.tipo === 'trabalho_interrompida' || item.tipo === 'agente_atencao')
    return <AlertTriangle size={size} style={{ color: 'var(--color-warning)' }} />;
  if (item.tipo === 'trabalho_plano') return <ListChecks size={size} style={{ color: 'var(--color-accent)' }} />;
  if (item.tipo.startsWith('trabalho')) return <Briefcase size={size} style={{ color: 'var(--color-warning)' }} />;
  if (item.tipo.startsWith('agente')) return <Bot size={size} style={{ color: 'var(--color-accent)' }} />;
  return <Bell size={size} style={{ color: 'var(--color-accent)' }} />;
}

function Row({
  item,
  last,
  onDone,
  onOpen,
}: {
  item: InboxItem;
  last: boolean;
  onDone: (ids: string[]) => void;
  onOpen: (item: InboxItem) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [details, setDetails] = useState(false);
  const [error, setError] = useState('');

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
      onDone([item.id]);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t('caixa.failed'));
    } finally {
      setBusy(false);
    }
  };

  const tier = TIER_STYLES[String(item.extra.tier ?? '')] ?? TIER_STYLES.medium;
  const payload = item.extra.payload as Record<string, unknown> | undefined;
  const hasPayload = item.tipo === 'aprovacao' && payload && Object.keys(payload).length > 0;
  const isNotice = item.categoria === 'aviso';

  return (
    <div
      className="px-4 py-3"
      style={{ borderBottom: last ? 'none' : '1px solid var(--color-border)' }}
      data-testid={`inbox-item-${item.tipo}`}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0">
          <KindIcon item={item} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
              {t(`caixa.kinds.${item.tipo}`)}
            </span>
            <span className="text-[10px] flex items-center gap-0.5 shrink-0" style={{ color: 'var(--color-text-secondary)' }}>
              <Clock size={9} />
              {timeAgo(item.quando)}
            </span>
          </div>
          {item.titulo && (
            <p className="text-[13px] leading-snug break-words mt-0.5" style={{ color: 'var(--color-text)' }}>
              {item.tipo === 'aprovacao' ? item.texto : item.titulo}
            </p>
          )}
          {item.tipo === 'aprovacao' && (
            <span
              className="inline-block mt-1 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
              style={{ background: tier.bg, color: tier.color }}
            >
              {item.titulo} · {t(`common.approvals.tier.${String(item.extra.tier ?? 'medium')}`)}
            </span>
          )}
          {item.tipo !== 'aprovacao' && item.texto && (
            <p
              className="text-xs mt-1 whitespace-pre-wrap break-words line-clamp-4"
              style={{ color: item.tipo === 'trabalho_pergunta' ? 'var(--color-text)' : 'var(--color-text-secondary)' }}
            >
              {item.texto}
            </p>
          )}
        </div>
        {isNotice && (
          <button
            type="button"
            onClick={() => void act(() => dispensarAvisos([item.id]))}
            disabled={busy}
            className="p-0.5 rounded cursor-pointer shrink-0"
            style={{ color: 'var(--color-text-tertiary)' }}
            aria-label={t('caixa.dismiss')}
            title={t('caixa.dismiss')}
            data-testid="inbox-dismiss"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {hasPayload && (
        <>
          <button
            className="flex items-center gap-1 text-[11px] mt-1.5 cursor-pointer"
            style={{ color: 'var(--color-text-secondary)' }}
            onClick={() => setDetails((d) => !d)}
          >
            {details ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {details ? t('common.approvals.hideDetails') : t('common.approvals.viewDetails')}
          </button>
          {details && (
            <pre
              className="text-[10px] rounded-lg p-2.5 mt-1.5 overflow-x-auto"
              style={{
                background: 'var(--color-bg-tertiary)',
                color: 'var(--color-text-secondary)',
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {JSON.stringify(payload, null, 2)}
            </pre>
          )}
        </>
      )}

      <div className="flex gap-2 mt-2.5">
        {item.tipo === 'aprovacao' && (
          <>
            <button onClick={() => void act(() => approveAction(item.ref))} disabled={busy} className={actionClass} style={yes} data-testid="inbox-approve">
              <CheckCircle size={12} /> {t('common.approvals.approve')}
            </button>
            <button onClick={() => void act(() => denyAction(item.ref))} disabled={busy} className={actionClass} style={no}>
              <XCircle size={12} /> {t('common.approvals.deny')}
            </button>
          </>
        )}
        {item.tipo === 'trabalho_pergunta' && (
          <>
            <button onClick={() => void act(() => responderTarefa(item.ref, true))} disabled={busy} className={actionClass} style={yes} data-testid="inbox-yes">
              {t('caixa.yes')}
            </button>
            <button onClick={() => void act(() => responderTarefa(item.ref, false))} disabled={busy} className={actionClass} style={no} data-testid="inbox-no">
              {t('caixa.no')}
            </button>
          </>
        )}
        {item.link && item.tipo !== 'aprovacao' && item.tipo !== 'trabalho_pergunta' && (
          <button onClick={() => onOpen(item)} className={actionClass} style={neutral} data-testid="inbox-open">
            {t(item.tipo === 'trabalho_plano' ? 'caixa.reviewPlan' : 'caixa.open')}
          </button>
        )}
      </div>
      {error && (
        <p className="text-[11px] mt-1.5" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </div>
  );
}

/** Sininho no topo: o que precisa de você e o que aconteceu enquanto isso. */
export function InboxBell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const caixa = useCaixa((s) => s.caixa);
  const remover = useCaixa((s) => s.remover);
  const atualizar = useCaixa((s) => s.atualizar);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    void atualizar();
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, atualizar]);

  const decisoes = caixa?.decisoes ?? [];
  const avisos = caixa?.avisos ?? [];
  const pending = decisoes.length;
  const total = pending + avisos.length;

  const done = (ids: string[]) => {
    remover(ids);
    void atualizar();
  };

  const openItem = (item: InboxItem) => {
    setOpen(false);
    if (item.categoria === 'aviso') {
      remover([item.id]);
      void dispensarAvisos([item.id]).catch(() => undefined);
    }
    navigate(item.link, item.tipo.startsWith('trabalho') ? { state: { tarefa: item.ref } } : undefined);
  };

  const clearNotices = async () => {
    remover(avisos.map((a) => a.id));
    try {
      await dispensarAvisos('todos');
    } finally {
      void atualizar();
    }
  };

  const title = pending > 0 ? t('caixa.titleWaiting', { n: pending }) : t('caixa.title');

  return (
    <div ref={containerRef} className="fixed top-2 right-3 z-40">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-lg transition-colors cursor-pointer"
        title={title}
        aria-label={title}
        aria-expanded={open}
        data-testid="inbox-bell"
        style={{
          color: total > 0 ? 'var(--color-text)' : 'var(--color-text-secondary)',
          background: open
            ? 'var(--color-bg-tertiary)'
            : pending > 0
              ? 'color-mix(in srgb, var(--color-error) 8%, transparent)'
              : 'transparent',
        }}
      >
        <Bell size={17} />
        {pending > 0 ? (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full text-[10px] font-bold px-1 leading-none"
            style={{ background: 'var(--color-error)', color: '#fff' }}
            data-testid="inbox-count"
          >
            {pending > 99 ? '99+' : pending}
          </span>
        ) : avisos.length > 0 ? (
          <span
            className="absolute top-1 right-1 w-2 h-2 rounded-full"
            style={{ background: 'var(--color-accent)' }}
            data-testid="inbox-dot"
          />
        ) : null}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-1 rounded-xl shadow-2xl overflow-hidden flex flex-col"
          style={{
            width: 'min(360px, calc(100vw - 24px))',
            maxHeight: 'min(560px, calc(100vh - 80px))',
            background: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
          }}
          role="dialog"
          aria-label={t('caixa.title')}
        >
          <div className="flex items-center justify-between px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
            <div className="flex items-center gap-2">
              <Bell size={13} style={{ color: 'var(--color-accent)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                {t('caixa.title')}
              </span>
            </div>
            {avisos.length > 0 && (
              <button
                onClick={() => void clearNotices()}
                className="text-[11px] cursor-pointer"
                style={{ color: 'var(--color-text-secondary)' }}
                data-testid="inbox-clear"
              >
                {t('caixa.clearNotices')}
              </button>
            )}
          </div>

          <div className="overflow-y-auto flex-1">
            {total === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 gap-2">
                <CheckCircle size={26} style={{ color: 'var(--color-text-secondary)', opacity: 0.35 }} />
                <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {t('caixa.empty')}
                </span>
              </div>
            ) : (
              <>
                {pending > 0 && (
                  <section data-testid="inbox-decisions">
                    <h3 className="px-4 pt-3 text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-error)' }}>
                      {t('caixa.needsYou', { n: pending })}
                    </h3>
                    {decisoes.map((item, i) => (
                      <Row key={item.id} item={item} last={i === decisoes.length - 1 && avisos.length === 0} onDone={done} onOpen={openItem} />
                    ))}
                  </section>
                )}
                {avisos.length > 0 && (
                  <section data-testid="inbox-notices">
                    <h3 className="px-4 pt-3 text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
                      {t('caixa.notices')}
                    </h3>
                    {avisos.map((item, i) => (
                      <Row key={item.id} item={item} last={i === avisos.length - 1} onDone={done} onOpen={openItem} />
                    ))}
                  </section>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
