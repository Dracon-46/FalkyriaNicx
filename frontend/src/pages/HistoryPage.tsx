import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bell,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  FileText,
  FolderKanban,
  FolderTree,
  History,
  MessageSquare,
  Repeat,
  Search,
  ShieldAlert,
  ShieldCheck,
  StickyNote,
  Undo2,
  Wrench,
  Zap,
} from 'lucide-react';
import {
  ACTIVITY_TYPES,
  desfazerAtividade,
  listarHistorico,
  verificarIntegridade,
  type Activity,
  type ActivityType,
  type Integrity,
  type UndoResult,
} from '../lib/historico';

type Tab = 'atividades' | 'auditoria';

const AUDIT_TYPES: ActivityType[] = ['acao', 'ferramenta'];
const PAGE_SIZE = 50;

const TYPE_ICONS: Record<ActivityType, typeof History> = {
  conversa: MessageSquare,
  nota: StickyNote,
  lembrete: Bell,
  agenda: CalendarDays,
  projeto: FolderKanban,
  arquivo: FileText,
  organizacao: FolderTree,
  acao: Zap,
  ferramenta: Wrench,
  desfazer: Undo2,
  rotina: Repeat,
};

const RESULT_COLORS: Record<string, string> = {
  pendente: 'var(--color-warning)',
  bloqueado: 'var(--color-warning)',
  falhou: 'var(--color-error)',
};

const card = {
  background: 'var(--color-bg-secondary)',
  border: '1px solid var(--color-border)',
} as const;
const input = {
  background: 'var(--color-bg)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
} as const;
const buttonClass =
  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default';
const secondaryButton = {
  background: 'var(--color-bg-secondary)',
  color: 'var(--color-text-secondary)',
  border: '1px solid var(--color-border)',
} as const;
const chip = 'text-[10px] px-1.5 py-0.5 rounded shrink-0';

/** AAAA-MM-DD do dia local (o `quando` do registro também é hora local). */
function dayKey(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** "Hoje", "Ontem" ou a data por extenso no idioma da interface. */
function dayLabel(key: string, lang: string, names: { today: string; yesterday: string }): string {
  const today = new Date();
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  if (key === dayKey(today)) return names.today;
  if (key === dayKey(yesterday)) return names.yesterday;
  const [y, m, d] = key.split('-').map(Number);
  const date = new Date(y, (m ?? 1) - 1, d ?? 1);
  if (Number.isNaN(date.getTime())) return key;
  return date.toLocaleDateString(lang, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    ...(y === today.getFullYear() ? {} : { year: 'numeric' }),
  });
}

function groupByDay(items: Activity[]): [string, Activity[]][] {
  const groups = new Map<string, Activity[]>();
  for (const item of items) {
    const key = item.quando.slice(0, 10);
    const list = groups.get(key);
    if (list) list.push(item);
    else groups.set(key, [item]);
  }
  return [...groups.entries()];
}

function text(value: unknown): string {
  if (value === null || value === undefined) return '';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** Detalhe de uma linha da auditoria: ferramenta, argumentos e resposta. */
function AuditDetail({ item }: { item: Activity }) {
  const { t } = useTranslation();
  const d = item.detalhe ?? {};
  const args = d.argumentos && typeof d.argumentos === 'object' ? Object.entries(d.argumentos as Record<string, unknown>) : [];
  const response = text(d.resposta);
  const rows: [string, string][] = [];
  if (d.ferramenta) rows.push([t('historico.audit.tool'), text(d.ferramenta)]);
  if (d.acao) rows.push([t('historico.audit.action'), text(d.acao)]);
  if (d.op) rows.push([t('historico.audit.operation'), text(d.op)]);
  if (d.alvo) rows.push([t('historico.audit.target'), text(d.alvo)]);
  if (d.risco) rows.push([t('historico.audit.risk'), t(`historico.risks.${text(d.risco)}`, { defaultValue: text(d.risco) })]);

  return (
    <div
      className="mt-2 text-xs space-y-2"
      style={{ color: 'var(--color-text-secondary)', marginInlineStart: 45 }}
      data-testid="audit-detail"
    >
      {rows.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt style={{ color: 'var(--color-text-tertiary)' }}>{label}</dt>
              <dd className="break-words font-mono">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {args.length > 0 && (
        <div>
          <div style={{ color: 'var(--color-text-tertiary)' }}>{t('historico.audit.arguments')}</div>
          <table className="mt-1 w-full text-left">
            <tbody>
              {args.map(([name, value]) => (
                <tr key={name} style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
                  <td className="py-0.5 pr-3 align-top font-mono whitespace-nowrap">{name}</td>
                  <td className="py-0.5 font-mono break-all">{text(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {response && (
        <div>
          <div style={{ color: 'var(--color-text-tertiary)' }}>{t('historico.audit.response')}</div>
          <pre
            className="mt-1 px-2 py-1.5 rounded font-mono whitespace-pre-wrap break-words max-h-40 overflow-y-auto"
            style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border-subtle)' }}
          >
            {response.length > 600 ? `${response.slice(0, 600)}…` : response}
          </pre>
        </div>
      )}
      {rows.length === 0 && args.length === 0 && !response && <div>{t('historico.audit.noDetail')}</div>}
    </div>
  );
}

function Row({
  item,
  audit,
  undoing,
  onUndo,
}: {
  item: Activity;
  audit: boolean;
  undoing: boolean;
  onUndo: (item: Activity) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const Icon = TYPE_ICONS[item.tipo] ?? History;
  const undone = Boolean(item.desfeito_em);
  const resultColor = RESULT_COLORS[item.resultado];

  return (
    <li className="py-2.5" style={{ borderBottom: '1px solid var(--color-border-subtle)' }} data-testid={`history-item-${item.id}`}>
      <div className="flex items-center gap-2 min-w-0">
        {audit ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={t(open ? 'historico.audit.hideDetail' : 'historico.audit.showDetail')}
            className="shrink-0 cursor-pointer"
            style={{ color: 'var(--color-text-tertiary)' }}
            data-testid={`history-expand-${item.id}`}
          >
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : null}
        <Icon
          size={15}
          className="shrink-0"
          style={{ color: undone ? 'var(--color-text-tertiary)' : 'var(--color-accent)' }}
          aria-label={t(`historico.types.${item.tipo}`, { defaultValue: item.tipo })}
        />
        <span
          className="flex-1 min-w-0 text-sm break-words"
          style={{
            color: undone ? 'var(--color-text-tertiary)' : 'var(--color-text)',
            textDecoration: undone ? 'line-through' : 'none',
          }}
        >
          {item.titulo}
        </span>
        <span className="text-xs shrink-0 tabular-nums" style={{ color: 'var(--color-text-tertiary)' }}>
          {item.quando.slice(11, 16)}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 mt-1" style={{ marginInlineStart: audit ? 45 : 23 }}>
        {item.origem && (
          <span className={chip} style={secondaryButton}>
            {t(`historico.origins.${item.origem}`, { defaultValue: item.origem })}
          </span>
        )}
        {audit && item.nivel && (
          <span className={chip} style={secondaryButton}>
            {t(`historico.levels.${item.nivel}`, { defaultValue: item.nivel })}
          </span>
        )}
        {(audit || resultColor) && (
          <span
            className={chip}
            style={{ border: `1px solid ${resultColor ?? 'var(--color-border)'}`, color: resultColor ?? 'var(--color-success)' }}
            data-testid={`history-result-${item.id}`}
          >
            {t(`historico.results.${item.resultado}`, { defaultValue: item.resultado })}
          </span>
        )}
        {undone && (
          <span className={chip} style={{ color: 'var(--color-text-tertiary)' }}>
            {t('historico.undone')}
          </span>
        )}
        {item.desfazivel && !undone && (
          <button
            type="button"
            onClick={() => onUndo(item)}
            disabled={undoing}
            className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded cursor-pointer disabled:opacity-50 disabled:cursor-default"
            style={secondaryButton}
            data-testid={`history-undo-${item.id}`}
          >
            <Undo2 size={11} /> {t('historico.undo')}
          </button>
        )}
      </div>
      {audit && open && <AuditDetail item={item} />}
    </li>
  );
}

export function HistoryPage() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>('atividades');
  const [search, setSearch] = useState('');
  const [busca, setBusca] = useState('');
  const [tipos, setTipos] = useState<ActivityType[]>([]);
  const [desde, setDesde] = useState('');
  const [ate, setAte] = useState('');
  const [items, setItems] = useState<Activity[]>([]);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState<UndoResult | null>(null);
  const [undoing, setUndoing] = useState(false);
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const request = useRef(0);

  // Busca só depois de uma pausa na digitação.
  useEffect(() => {
    const timer = setTimeout(() => setBusca(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const audit = tab === 'auditoria';
  // Em texto: a lista muda de identidade a cada render.
  const chosen = (audit ? AUDIT_TYPES : tipos).join(',');

  const load = useCallback(
    async (before?: number) => {
      const id = ++request.current;
      if (before === undefined) setLoading(true);
      else setLoadingMore(true);
      try {
        const page = await listarHistorico({
          busca,
          tipos: chosen ? chosen.split(',') : [],
          desde: desde || undefined,
          ate: ate || undefined,
          limite: PAGE_SIZE,
          antesDe: before,
        });
        if (id !== request.current) return;
        setItems((current) => (before === undefined ? page.itens : [...current, ...page.itens]));
        setMore(page.mais);
        setError('');
      } catch (e) {
        if (id !== request.current) return;
        setError(e instanceof Error ? e.message : t('historico.loadFailed'));
        if (before === undefined) setItems([]);
        setMore(false);
      } finally {
        if (id === request.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [busca, chosen, desde, ate, t],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!audit) return;
    let cancelled = false;
    verificarIntegridade()
      .then((r) => {
        if (!cancelled) setIntegrity(r);
      })
      .catch(() => {
        if (!cancelled) setIntegrity(null);
      });
    return () => {
      cancelled = true;
    };
  }, [audit, items]);

  const undo = async (item: Activity) => {
    setUndoing(true);
    try {
      setNotice(await desfazerAtividade(item.id, i18n.language));
      await load();
    } catch (e) {
      setNotice({ ok: false, mensagem: e instanceof Error ? e.message : t('historico.undoFailed') });
    } finally {
      setUndoing(false);
    }
  };

  const toggleType = (tipo: ActivityType) =>
    setTipos((current) => (current.includes(tipo) ? current.filter((x) => x !== tipo) : [...current, tipo]));

  const filtered = Boolean(busca.trim() || desde || ate || (!audit && tipos.length));
  const groups = groupByDay(items);
  const tabs: Tab[] = ['atividades', 'auditoria'];

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-5">
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
            <History size={18} /> {t('historico.title')}
          </h1>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            {t('historico.subtitle')}
          </p>
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('historico.hint')}
          </p>
        </header>

        <div className="flex gap-1 mb-4" role="tablist" aria-label={t('historico.title')}>
          {tabs.map((value) => {
            const active = tab === value;
            return (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setTab(value)}
                className={buttonClass}
                style={{
                  ...secondaryButton,
                  background: active ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                  color: active ? 'var(--color-text)' : 'var(--color-text-secondary)',
                  borderColor: active ? 'var(--color-accent)' : 'var(--color-border)',
                }}
                data-testid={`history-tab-${value}`}
              >
                {value === 'auditoria' ? <ShieldCheck size={12} /> : <History size={12} />}
                {t(`historico.tabs.${value}`)}
              </button>
            );
          })}
        </div>

        <div className="rounded-xl p-4 mb-4 space-y-3" style={card}>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex-1 min-w-0 flex items-center gap-2 px-3 py-1.5 rounded-lg" style={input}>
              <Search size={14} style={{ color: 'var(--color-text-tertiary)' }} />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('historico.searchPlaceholder')}
                aria-label={t('historico.search')}
                className="flex-1 min-w-0 bg-transparent outline-none text-sm"
                style={{ color: 'var(--color-text)' }}
                data-testid="history-search"
              />
            </div>
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <label className="flex items-center gap-1">
                {t('historico.from')}
                <input
                  type="date"
                  value={desde}
                  max={ate || undefined}
                  onChange={(e) => setDesde(e.target.value)}
                  className="px-2 py-1 rounded text-xs"
                  style={input}
                  data-testid="history-from"
                />
              </label>
              <label className="flex items-center gap-1">
                {t('historico.to')}
                <input
                  type="date"
                  value={ate}
                  min={desde || undefined}
                  onChange={(e) => setAte(e.target.value)}
                  className="px-2 py-1 rounded text-xs"
                  style={input}
                  data-testid="history-to"
                />
              </label>
            </div>
          </div>
          {!audit && (
            <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('historico.typesLabel')}>
              {ACTIVITY_TYPES.map((tipo) => {
                const on = tipos.includes(tipo);
                const Icon = TYPE_ICONS[tipo];
                return (
                  <button
                    key={tipo}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleType(tipo)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer"
                    style={{
                      background: on ? 'var(--color-accent)' : 'var(--color-bg)',
                      color: on ? '#fff' : 'var(--color-text-secondary)',
                      border: '1px solid var(--color-border)',
                    }}
                    data-testid={`history-type-${tipo}`}
                  >
                    <Icon size={11} /> {t(`historico.types.${tipo}`)}
                  </button>
                );
              })}
            </div>
          )}
          {audit && integrity && (
            <div
              className="flex items-center gap-1.5 text-xs"
              style={{ color: integrity.ok ? 'var(--color-success)' : 'var(--color-warning)' }}
              data-testid="history-integrity"
            >
              {integrity.ok ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}
              {integrity.ok
                ? t('historico.integrity.ok', { n: integrity.linhas })
                : t('historico.integrity.broken', { id: integrity.quebra_em ?? '?' })}
            </div>
          )}
        </div>

        {notice && (
          <div
            className="mb-4 text-sm rounded-lg px-3 py-2 flex items-start justify-between gap-3"
            role="status"
            style={{ ...card, color: notice.ok ? 'var(--color-text)' : 'var(--color-error)' }}
            data-testid="history-notice"
          >
            <span className="min-w-0 break-words">{notice.mensagem}</span>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="text-xs shrink-0 cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              {t('historico.dismiss')}
            </button>
          </div>
        )}

        {error && (
          <div className="mb-4 text-sm rounded-lg px-3 py-2" role="alert" style={{ ...card, color: 'var(--color-error)' }}>
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }} data-testid="history-loading">
            {t('historico.loading')}
          </p>
        ) : items.length === 0 && !error ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }} data-testid="history-empty">
            {filtered ? t('historico.noMatches') : t(audit ? 'historico.audit.empty' : 'historico.empty')}
          </p>
        ) : (
          <div className="space-y-5" data-testid="history-list">
            {groups.map(([day, list]) => (
              <section key={day}>
                <h2
                  className="text-xs font-semibold uppercase tracking-wide mb-1"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  {dayLabel(day, i18n.language, { today: t('historico.today'), yesterday: t('historico.yesterday') })}
                </h2>
                <ul>
                  {list.map((item) => (
                    <Row key={item.id} item={item} audit={audit} undoing={undoing} onUndo={(it) => void undo(it)} />
                  ))}
                </ul>
              </section>
            ))}
            {more && (
              <button
                type="button"
                onClick={() => void load(items[items.length - 1]?.id)}
                disabled={loadingMore}
                className={`${buttonClass} mx-auto`}
                style={secondaryButton}
                data-testid="history-more"
              >
                {loadingMore ? t('historico.loading') : t('historico.loadMore')}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default HistoryPage;
