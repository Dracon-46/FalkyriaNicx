import { describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({ apiFetch: vi.fn() }));
vi.mock('@supabase/supabase-js', () => ({ createClient: vi.fn() }));

import {
  PainelAccessError,
  computeKpis,
  dailySeries,
  daysOf,
  fetchPainelData,
  isEmpty,
  painelErrorMessage,
  relativeChange,
  todayInSaoPaulo,
  type PainelData,
} from './painel';

/** A query builder stub: every chained call returns itself; awaiting yields `result`. */
function builder(result: { data: unknown; error: unknown }) {
  const b: Record<string, unknown> = {};
  for (const name of ['select', 'gte', 'order', 'limit']) b[name] = () => b;
  b.then = (resolve: (v: unknown) => unknown, reject: (e: unknown) => unknown) =>
    Promise.resolve(result).then(resolve, reject);
  return b;
}

function clientWith(tables: Record<string, { data: unknown; error: unknown }>) {
  return {
    from: (table: string) => builder(tables[table] ?? { data: [], error: null }),
    rpc: async (fn: string) => tables[fn] ?? { data: null, error: null },
  } as never;
}

const base = (over: Partial<PainelData> = {}): PainelData => ({
  period: 7,
  today: '2026-10-23',
  activity: [],
  usage: [],
  features: [],
  errorClasses: [],
  activeInstallations: null,
  platforms: [],
  funnel: null,
  consent: [],
  recent: [],
  ...over,
});

describe('painel data', () => {
  it('buckets "today" in São Paulo time', () => {
    // 02:00 UTC on the 24th is still the 23rd in Brasília.
    expect(todayInSaoPaulo(new Date('2026-10-24T02:00:00Z'))).toBe('2026-10-23');
    expect(daysOf(3, '2026-11-01')).toEqual(['2026-10-30', '2026-10-31', '2026-11-01']);
  });

  it('fills days without events with zeros', () => {
    const series = dailySeries(
      base({
        activity: [{ day: '2026-10-21', installations: 3, app_opens: 5, chat_sessions: 4, errors: 1, events: 9 }],
        usage: [
          {
            day: '2026-10-23', turns: 2, tokens_in: 100, tokens_out: 40, tool_calls: 0,
            latency_ms_p50: null, latency_ms_p95: null, duration_ms: 0,
          },
        ],
      }),
    );
    expect(series).toHaveLength(7);
    expect(series[0]).toMatchObject({ day: '2026-10-17', installations: 0, tokens_in: 0 });
    expect(series[4]).toMatchObject({ day: '2026-10-21', installations: 3, chat_sessions: 4 });
    expect(series[6]).toMatchObject({ day: '2026-10-23', tokens_in: 100, tokens_out: 40 });
  });

  it('compares the period with the same span right before it', () => {
    const row = (day: string, chat_sessions: number, installations = 1) => ({
      day, installations, app_opens: 0, chat_sessions, errors: 0, events: 0,
    });
    const kpis = computeKpis(
      base({ activity: [row('2026-10-10', 4, 7), row('2026-10-20', 6, 14), row('2026-10-23', 2)] }),
    );
    expect(kpis.chatSessions).toEqual({ current: 8, previous: 4 });
    expect(relativeChange(kpis.chatSessions)).toBe(1);
    expect(kpis.installations.current).toBeCloseTo(15 / 7);
    expect(relativeChange({ current: 3, previous: 0 })).toBeNull();
  });

  it('reads every view and maps a permission error to PainelAccessError', async () => {
    const ok = await fetchPainelData(clientWith({}), 30, '2026-10-23');
    expect(isEmpty(ok)).toBe(true);
    expect(ok.funnel).toBeNull();

    await expect(
      fetchPainelData(
        clientWith({ nicx_events: { data: null, error: { code: '42501', message: 'permission denied' } } }),
        7,
        '2026-10-23',
      ),
    ).rejects.toBeInstanceOf(PainelAccessError);
  });

  it('translates Supabase errors to Portuguese', () => {
    expect(painelErrorMessage({ code: 'invalid_credentials', message: 'Invalid login credentials' })).toBe(
      'E-mail ou senha incorretos.',
    );
    expect(painelErrorMessage({ message: 'Email not confirmed' })).toContain('E-mail ainda não confirmado');
    expect(painelErrorMessage({ name: 'AuthRetryableFetchError', status: 0, message: 'Failed to fetch' })).toContain(
      'Sem conexão',
    );
  });
});

describe('period summary', () => {
  it('uses distinct installations and period-scoped features from nicx_period_summary', async () => {
    const data = await fetchPainelData(
      clientWith({
        nicx_period_summary: {
          data: {
            installations: 12,
            installations_prev: 8,
            features: [{ feature: 'voice', uses: 5, installations: 3, last_used_at: '2026-10-23T10:00:00Z' }],
            error_classes: [{ error_class: 'network_error', occurrences: 2, installations: 1, last_seen_at: null }],
          },
          error: null,
        },
      }),
      7,
      '2026-10-23',
    );
    expect(data.activeInstallations).toEqual({ current: 12, previous: 8 });
    expect(computeKpis(data).installations).toEqual({ current: 12, previous: 8 });
    expect(data.features).toEqual([
      { feature: 'voice', uses: 5, installations: 3, last_used_at: '2026-10-23T10:00:00Z' },
    ]);
    expect(data.errorClasses[0]).toMatchObject({ error_class: 'network_error', occurrences: 2 });
  });

  it('maps a permission error from the summary to PainelAccessError', async () => {
    await expect(
      fetchPainelData(
        clientWith({ nicx_period_summary: { data: null, error: { code: '42501', message: 'denied' } } }),
        30,
        '2026-10-23',
      ),
    ).rejects.toBeInstanceOf(PainelAccessError);
  });
});
