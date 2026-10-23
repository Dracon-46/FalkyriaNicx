import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';
import { ArrowDownRight, ArrowUpRight, Check, LogOut, Minus, RefreshCw } from 'lucide-react';
import {
  EMPTY_DATA_MESSAGE,
  ERROR_LABELS,
  EVENT_LABELS,
  FEATURE_LABELS,
  FUNNEL_STEPS,
  PERIODS,
  PainelAccessError,
  computeKpis,
  dailySeries,
  fetchPainelData,
  isEmpty,
  relativeChange,
  type Kpi,
  type PainelData,
  type Period,
} from '../../lib/painel';
import { NicxMascot } from '../Mascot/NicxMascot';
import { ChartCard, DailyAreaChart, EmptyState, FunnelSteps, Legend, RankedBars, StackedDailyColumns } from './charts';
import {
  fmtClock,
  fmtCompact,
  fmtDateTime,
  fmtDayLong,
  fmtInt,
  fmtPercent,
  fmtProperties,
  fmtSmall,
} from './format';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; data: PainelData; at: Date }
  | { kind: 'error'; message: string; data?: PainelData; at?: Date };

const RANKED_LIMIT = 8;

/** Top rows plus an "Outros" fold, so the bar list never grows past 9 rows. */
function ranked<T>(rows: T[], label: (r: T) => string, value: (r: T) => number) {
  const sorted = [...rows].sort((a, b) => value(b) - value(a));
  const top = sorted.slice(0, RANKED_LIMIT).map((r) => ({ label: label(r), value: value(r) }));
  const rest = sorted.slice(RANKED_LIMIT).reduce((acc, r) => acc + value(r), 0);
  return rest > 0 ? [...top, { label: 'Outros', value: rest }] : top;
}

// ---------------------------------------------------------------------------
// Header pieces
// ---------------------------------------------------------------------------

function PeriodPicker({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div
      role="radiogroup"
      aria-label="Período"
      className="inline-flex gap-0.5 p-0.5 rounded-lg"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      {PERIODS.map((p) => {
        const active = p === value;
        return (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(p)}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            style={{
              background: active ? 'var(--color-surface)' : 'transparent',
              color: active ? 'var(--color-text)' : 'var(--color-text-secondary)',
              boxShadow: active ? 'var(--shadow-sm)' : 'none',
            }}
          >
            {active && <Check size={12} strokeWidth={3} aria-hidden="true" />}
            {p} dias
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI tiles
// ---------------------------------------------------------------------------

function Delta({ kpi, period, upIsGood }: { kpi: Kpi; period: Period; upIsGood: boolean }) {
  const change = relativeChange(kpi);
  const versus = `vs. ${period} dias anteriores`;
  if (change === null) {
    return (
      <span style={{ color: 'var(--color-text-tertiary)' }}>
        {kpi.current > 0 ? `Sem dados nos ${period} dias anteriores` : 'Sem dados para comparar'}
      </span>
    );
  }
  if (Math.abs(change) < 0.005) {
    return (
      <span className="inline-flex items-center gap-1" style={{ color: 'var(--color-text-secondary)' }}>
        <Minus size={12} aria-hidden="true" /> Estável {versus}
      </span>
    );
  }
  const up = change > 0;
  const good = up === upIsGood;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className="inline-flex items-center gap-1"
      style={{ color: good ? 'var(--color-success)' : 'var(--color-error)' }}
    >
      <Icon size={12} aria-hidden="true" />
      <span>
        {up ? '+' : '−'}
        {fmtPercent(Math.abs(change))}
      </span>
      <span style={{ color: 'var(--color-text-secondary)' }}>{versus}</span>
    </span>
  );
}

function KpiTile({
  label,
  hint,
  value,
  kpi,
  period,
  upIsGood = true,
}: {
  label: string;
  hint?: string;
  value: string;
  kpi: Kpi;
  period: Period;
  upIsGood?: boolean;
}) {
  return (
    <div className="hud-panel p-4 min-w-0">
      <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {label}
        {hint && <span style={{ color: 'var(--color-text-tertiary)' }}> · {hint}</span>}
      </div>
      <div className="text-2xl font-semibold mt-1 truncate" style={{ color: 'var(--color-text)' }}>
        {value}
      </div>
      <div className="text-xs mt-1.5">
        <Delta kpi={kpi} period={period} upIsGood={upIsGood} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

function Table({ head, children, caption }: { head: (string | { label: string; num?: boolean })[]; children: React.ReactNode; caption?: string }) {
  return (
    <table className="painel-table">
      {caption && <caption className="sr-only">{caption}</caption>}
      <thead>
        <tr>
          {head.map((h) => {
            const cell = typeof h === 'string' ? { label: h } : h;
            return (
              <th key={cell.label} scope="col" className={cell.num ? 'num' : undefined}>
                {cell.label}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

function SectionHeading({ id, title, note }: { id: string; title: string; note?: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-3">
      <h2 id={id} className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {title}
      </h2>
      {note && (
        <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {note}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

interface PainelDashboardProps {
  client: SupabaseClient;
  onAccessDenied: () => void;
}

export function PainelDashboard({ client, onAccessDenied }: PainelDashboardProps) {
  const [period, setPeriod] = useState<Period>(() => {
    try {
      const saved = Number(localStorage.getItem('nicx-painel-period'));
      return (PERIODS as readonly number[]).includes(saved) ? (saved as Period) : 30;
    } catch {
      return 30;
    }
  });
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [refreshing, setRefreshing] = useState(false);
  const requestId = useRef(0);

  const load = useCallback(
    async (p: Period) => {
      const id = ++requestId.current;
      setRefreshing(true);
      try {
        const data = await fetchPainelData(client, p);
        if (id === requestId.current) setState({ kind: 'ready', data, at: new Date() });
      } catch (error) {
        if (id !== requestId.current) return;
        if (error instanceof PainelAccessError) {
          onAccessDenied();
          return;
        }
        const message = error instanceof Error ? error.message : 'Não foi possível carregar os dados.';
        setState((prev) =>
          prev.kind === 'ready'
            ? { kind: 'error', message, data: prev.data, at: prev.at }
            : { kind: 'error', message },
        );
      } finally {
        if (id === requestId.current) setRefreshing(false);
      }
    },
    [client, onAccessDenied],
  );

  useEffect(() => {
    void load(period);
    try {
      localStorage.setItem('nicx-painel-period', String(period));
    } catch {
      // Remembering the period is only a convenience.
    }
  }, [load, period]);

  const data = state.kind === 'ready' ? state.data : state.kind === 'error' ? state.data : undefined;
  const at = state.kind === 'ready' ? state.at : state.kind === 'error' ? state.at : undefined;

  return (
    <div className="flex flex-col gap-6">
      {/* Filter row: scopes the "Atividade" section below. */}
      <div className="flex flex-wrap items-center gap-3">
        <PeriodPicker value={period} onChange={setPeriod} />
        <button
          type="button"
          onClick={() => void load(period)}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors disabled:opacity-60 disabled:cursor-default focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          style={{
            background: 'var(--color-bg-secondary)',
            color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
          }}
        >
          <RefreshCw size={13} aria-hidden="true" className={refreshing ? 'animate-spin motion-reduce:animate-none' : undefined} />
          Atualizar
        </button>
        <span className="text-xs" role="status" style={{ color: 'var(--color-text-tertiary)' }}>
          {refreshing ? 'Carregando...' : at ? `Atualizado às ${fmtClock(at)}` : ''}
        </span>
      </div>

      {state.kind === 'error' && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg px-4 py-3 text-sm"
          style={{
            background: 'color-mix(in srgb, var(--color-error) 8%, transparent)',
            border: '1px solid color-mix(in srgb, var(--color-error) 20%, transparent)',
            color: 'var(--color-text)',
          }}
        >
          <span className="flex-1 min-w-0">{state.message}</span>
          <button
            type="button"
            onClick={() => void load(period)}
            className="text-xs underline cursor-pointer"
            style={{ color: 'var(--color-accent)' }}
          >
            Tentar de novo
          </button>
        </div>
      )}

      {!data && state.kind === 'loading' && <DashboardSkeleton />}

      {data && (
        <div className={refreshing ? 'painel-refreshing' : undefined} aria-busy={refreshing}>
          <DashboardBody data={data} period={data.period} />
        </div>
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-4" role="status" aria-label="Carregando o painel">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="hud-panel data-skeleton h-[104px]" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="hud-panel data-skeleton h-[268px]" />
        <div className="hud-panel data-skeleton h-[268px]" />
      </div>
    </div>
  );
}

function DashboardBody({ data, period }: { data: PainelData; period: Period }) {
  const series = useMemo(() => dailySeries(data), [data]);
  const kpis = useMemo(() => computeKpis(data), [data]);
  const empty = isEmpty(data);

  const hasActivity = series.some((d) => d.installations > 0 || d.chat_sessions > 0);
  const hasTokens = series.some((d) => d.tokens_in > 0 || d.tokens_out > 0);
  const features = ranked(data.features, (r) => FEATURE_LABELS[r.feature] ?? r.feature, (r) => r.uses);
  const errors = ranked(
    data.errorClasses,
    (r) => ERROR_LABELS[r.error_class] ?? r.error_class,
    (r) => r.occurrences,
  );
  const funnel = FUNNEL_STEPS.map((s) => ({ label: s.label, value: data.funnel?.[s.key] ?? 0 }));
  const funnelEmpty = funnel.every((s) => s.value === 0);

  const dailyTable = (key: 'installations' | 'chat_sessions', label: string) => (
    <Table head={['Dia', { label, num: true }]} caption={label}>
      {series.map((d) => (
        <tr key={d.day}>
          <td>{fmtDayLong(d.day)}</td>
          <td className="num">{fmtInt(d[key])}</td>
        </tr>
      ))}
    </Table>
  );

  return (
    <div className="flex flex-col gap-8">
      {empty && (
        <div
          className="flex items-center gap-4 rounded-xl px-5 py-4"
          style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-border)' }}
        >
          <NicxMascot size={56} mood="idle" decorative className="shrink-0" />
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              Tudo pronto, só falta chegar o primeiro evento.
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>
              {EMPTY_DATA_MESSAGE}
            </p>
          </div>
        </div>
      )}

      <section aria-labelledby="painel-atividade">
        <SectionHeading
          id="painel-atividade"
          title={`Atividade nos últimos ${period} dias`}
          note="Dias no horário de Brasília. Variação contra o mesmo número de dias logo antes."
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <KpiTile
            label="Instalações ativas"
            hint={data.activeInstallations ? undefined : 'média por dia'}
            value={
              data.activeInstallations
                ? fmtCompact(kpis.installations.current)
                : fmtSmall(Math.round(kpis.installations.current * 10) / 10)
            }
            kpi={kpis.installations}
            period={period}
          />
          <KpiTile
            label="Sessões de chat"
            value={fmtCompact(kpis.chatSessions.current)}
            kpi={kpis.chatSessions}
            period={period}
          />
          <KpiTile label="Tokens" value={fmtCompact(kpis.tokens.current)} kpi={kpis.tokens} period={period} />
          <KpiTile
            label="Erros exibidos"
            value={fmtCompact(kpis.errors.current)}
            kpi={kpis.errors}
            period={period}
            upIsGood={false}
          />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <ChartCard
            title="Instalações ativas por dia"
            subtitle="Instalações diferentes que enviaram algum evento"
            empty={!hasActivity}
            table={dailyTable('installations', 'Instalações')}
          >
            <DailyAreaChart data={series} dataKey="installations" name="instalações" />
          </ChartCard>
          <ChartCard
            title="Sessões de chat por dia"
            subtitle="Conversas encerradas no app ou no terminal"
            empty={!hasActivity}
            table={dailyTable('chat_sessions', 'Sessões')}
          >
            <DailyAreaChart data={series} dataKey="chat_sessions" name="sessões" />
          </ChartCard>
        </div>
        <ChartCard
          title="Tokens por dia"
          subtitle="Soma das sessões de chat: tokens lidos (entrada) e gerados (saída)"
          empty={!hasTokens}
          legend={
            <Legend
              items={[
                { label: 'Entrada', color: 'var(--viz-series-1)' },
                { label: 'Saída', color: 'var(--viz-series-2)' },
              ]}
            />
          }
          table={
            <Table head={['Dia', { label: 'Entrada', num: true }, { label: 'Saída', num: true }]} caption="Tokens por dia">
              {series.map((d) => (
                <tr key={d.day}>
                  <td>{fmtDayLong(d.day)}</td>
                  <td className="num">{fmtInt(d.tokens_in)}</td>
                  <td className="num">{fmtInt(d.tokens_out)}</td>
                </tr>
              ))}
            </Table>
          }
        >
          <StackedDailyColumns
            data={series}
            lower={{ key: 'tokens_in', name: 'entrada' }}
            upper={{ key: 'tokens_out', name: 'saída' }}
          />
        </ChartCard>
      </section>

      <section aria-labelledby="painel-uso">
        <SectionHeading
          id="painel-uso"
          title={`Recursos e erros nos últimos ${period} dias`}
          note="Mesmo período da atividade acima."
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <ChartCard
            title="Recursos mais usados"
            subtitle="Vezes em que cada recurso foi aberto"
            empty={features.length === 0}
            emptyText="Nenhum uso de recurso registrado ainda."
            table={
              <Table head={['Recurso', { label: 'Usos', num: true }, { label: 'Instalações', num: true }, 'Último uso']} caption="Recursos mais usados">
                {data.features.map((r) => (
                  <tr key={r.feature}>
                    <td>{FEATURE_LABELS[r.feature] ?? r.feature}</td>
                    <td className="num">{fmtInt(r.uses)}</td>
                    <td className="num">{fmtInt(r.installations)}</td>
                    <td>{fmtDateTime(r.last_used_at)}</td>
                  </tr>
                ))}
              </Table>
            }
          >
            <RankedBars rows={features} name="usos" />
          </ChartCard>
          <ChartCard
            title="Classes de erro"
            subtitle="Erros mostrados às pessoas, por tipo"
            empty={errors.length === 0}
            emptyText="Nenhum erro registrado. Bom sinal."
            table={
              <Table head={['Classe', { label: 'Ocorrências', num: true }, { label: 'Instalações', num: true }, 'Última vez']} caption="Classes de erro">
                {data.errorClasses.map((r) => (
                  <tr key={r.error_class}>
                    <td>
                      {ERROR_LABELS[r.error_class] ?? r.error_class}{' '}
                      <code className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                        {r.error_class}
                      </code>
                    </td>
                    <td className="num">{fmtInt(r.occurrences)}</td>
                    <td className="num">{fmtInt(r.installations)}</td>
                    <td>{fmtDateTime(r.last_seen_at)}</td>
                  </tr>
                ))}
              </Table>
            }
          >
            <RankedBars rows={errors} name="ocorrências" />
          </ChartCard>
        </div>
      </section>

      <section aria-labelledby="painel-historico">
        <SectionHeading id="painel-historico" title="Desde o início" note="Totais acumulados, sem filtro de período." />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <ChartCard
            title="Funil de instalação"
            subtitle="Instalações que chegaram a cada etapa; % sobre as que começaram"
            empty={funnelEmpty}
            emptyText="Nenhuma instalação registrada ainda."
          >
            <FunnelSteps steps={funnel} />
          </ChartCard>
          <ChartCard title="Consentimento" subtitle="Escolhas registradas, por versão da política" empty={data.consent.length === 0} emptyText="Nenhuma escolha registrada ainda.">
            <Table head={['Escolha', 'Política', { label: 'Registros', num: true }, 'Última']} caption="Consentimento">
              {data.consent.map((r) => (
                <tr key={`${r.granted}-${r.policy_version}`}>
                  <td>{r.granted === true ? 'Aceitou' : r.granted === false ? 'Recusou' : '—'}</td>
                  <td>{r.policy_version ?? '—'}</td>
                  <td className="num">{fmtInt(r.records)}</td>
                  <td>{fmtDateTime(r.last_at)}</td>
                </tr>
              ))}
            </Table>
          </ChartCard>
        </div>
      </section>

      <section aria-labelledby="painel-plataformas">
        <SectionHeading id="painel-plataformas" title="Plataformas e versões" note="Últimos 30 dias." />
        <div className="hud-panel p-4">
          {data.platforms.length === 0 ? (
            <EmptyState compact>Nenhuma instalação ativa nos últimos 30 dias.</EmptyState>
          ) : (
            <div className="overflow-x-auto">
              <Table head={['Plataforma', 'Sistema', 'Versão', { label: 'Instalações', num: true }, 'Visto por último']} caption="Plataformas e versões">
                {data.platforms.map((r) => (
                  <tr key={`${r.platform}-${r.os}-${r.app_version}`}>
                    <td>{r.platform}</td>
                    <td>{r.os}</td>
                    <td>{r.app_version}</td>
                    <td className="num">{fmtInt(r.installations)}</td>
                    <td>{fmtDateTime(r.last_seen_at)}</td>
                  </tr>
                ))}
              </Table>
            </div>
          )}
        </div>
      </section>

      <section aria-labelledby="painel-eventos">
        <SectionHeading id="painel-eventos" title="Eventos recentes" note="Os 50 mais novos, horário de Brasília." />
        <div className="hud-panel p-4">
          {data.recent.length === 0 ? (
            <EmptyState compact>{EMPTY_DATA_MESSAGE}</EmptyState>
          ) : (
            <div className="overflow-x-auto">
              <Table head={['Quando', 'Evento', 'Plataforma', 'Versão', 'Instalação', 'Detalhes']} caption="Eventos recentes">
                {data.recent.map((r) => (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap" style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {fmtDateTime(r.received_at)}
                    </td>
                    <td className="whitespace-nowrap">
                      {EVENT_LABELS[r.event] ?? r.event}
                    </td>
                    <td className="whitespace-nowrap">{[r.platform, r.os].filter(Boolean).join(' / ') || '—'}</td>
                    <td className="whitespace-nowrap">{r.app_version ?? '—'}</td>
                    <td>
                      <code className="text-[11px]" title={r.anon_id} style={{ color: 'var(--color-text-secondary)' }}>
                        {r.anon_id.slice(0, 8)}
                      </code>
                    </td>
                    <td className="min-w-[16rem]">
                      <code className="text-[11px] break-words" style={{ color: 'var(--color-text-secondary)' }}>
                        {fmtProperties(r.properties)}
                      </code>
                    </td>
                  </tr>
                ))}
              </Table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

/** Signed-in header actions, reused by the no-access screen. */
export function SignOutButton({ onSignOut, busy = false }: { onSignOut: () => void; busy?: boolean }) {
  return (
    <button
      type="button"
      onClick={onSignOut}
      disabled={busy}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
      style={{
        background: 'var(--color-bg-secondary)',
        color: 'var(--color-text)',
        border: '1px solid var(--color-border)',
      }}
    >
      <LogOut size={13} aria-hidden="true" /> Sair
    </button>
  );
}
