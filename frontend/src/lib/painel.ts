/**
 * Data layer of the Falkyria analytics dashboard ("Painel Falkyria").
 *
 * Reads the aggregated views of Falkyria's Supabase project with the signed
 * in administrator's session. Row level security does the gatekeeping: a
 * non-admin gets no rows (or "permission denied"), so this module only maps
 * results and errors into plain data and Portuguese messages.
 *
 * Imported only by the lazily loaded painel page, so supabase-js stays out
 * of the main bundle.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { fetchDashboardConfig } from './analytics';

export const PERIODS = [7, 30, 90] as const;
export type Period = (typeof PERIODS)[number];

export const EMPTY_DATA_MESSAGE =
  'Ainda não há dados — eles aparecem quando instalações com consentimento enviarem eventos.';

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

let clientPromise: Promise<SupabaseClient> | null = null;

/** Create (once) the Supabase client from the server's public settings. */
export function getPainelClient(): Promise<SupabaseClient> {
  if (!clientPromise) {
    const pending = (async () => {
      const config = await fetchDashboardConfig();
      if (!config.supabase_url || !config.supabase_key) {
        throw new Error('O painel não está configurado nesta instalação do Nicx.');
      }
      return createClient(config.supabase_url, config.supabase_key, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: false,
          storageKey: 'nicx-painel-auth',
        },
      });
    })();
    clientPromise = pending;
    pending.catch(() => {
      if (clientPromise === pending) clientPromise = null;
    });
  }
  return clientPromise;
}

// ---------------------------------------------------------------------------
// Errors in Portuguese
// ---------------------------------------------------------------------------

const AUTH_MESSAGES: Record<string, string> = {
  invalid_credentials: 'E-mail ou senha incorretos.',
  email_not_confirmed:
    'E-mail ainda não confirmado. Abra o link que enviamos para o seu e-mail e tente de novo.',
  user_already_exists: 'Já existe uma conta com este e-mail. Use "Entrar".',
  email_exists: 'Já existe uma conta com este e-mail. Use "Entrar".',
  weak_password: 'Senha fraca: use pelo menos 10 caracteres, misturando letras e números.',
  email_address_invalid: 'Este e-mail não é válido.',
  validation_failed: 'Confira o e-mail e a senha.',
  signup_disabled: 'A criação de contas está desativada no momento.',
  email_provider_disabled: 'O acesso por e-mail está desativado no momento.',
  over_request_rate_limit: 'Muitas tentativas seguidas. Aguarde um pouco e tente de novo.',
  over_email_send_rate_limit:
    'Muitos e-mails enviados há pouco. Aguarde alguns minutos e tente de novo.',
  user_banned: 'Esta conta está bloqueada.',
  session_expired: 'Sua sessão expirou. Entre de novo.',
  session_not_found: 'Sua sessão expirou. Entre de novo.',
  refresh_token_not_found: 'Sua sessão expirou. Entre de novo.',
  request_timeout: 'O servidor da Falkyria demorou demais para responder. Tente de novo.',
};

interface ErrorLike {
  code?: unknown;
  status?: unknown;
  name?: unknown;
  message?: unknown;
}

/** Translate a Supabase (auth or database) error into a user-facing message. */
export function painelErrorMessage(error: unknown): string {
  const e = (error ?? {}) as ErrorLike;
  const code = typeof e.code === 'string' ? e.code : '';
  const message = typeof e.message === 'string' ? e.message : '';
  if (code && AUTH_MESSAGES[code]) return AUTH_MESSAGES[code];
  if (/email not confirmed/i.test(message)) return AUTH_MESSAGES.email_not_confirmed;
  if (/invalid login credentials/i.test(message)) return AUTH_MESSAGES.invalid_credentials;
  if (/password should be at least/i.test(message)) return AUTH_MESSAGES.weak_password;
  if (/already registered/i.test(message)) return AUTH_MESSAGES.user_already_exists;
  if (code === '42501' || /permission denied/i.test(message)) {
    return 'Sua conta não tem acesso a estes dados.';
  }
  if (
    e.name === 'AuthRetryableFetchError' ||
    e.status === 0 ||
    /failed to fetch|networkerror|load failed|fetch failed/i.test(message)
  ) {
    return 'Sem conexão com os servidores da Falkyria. Verifique sua internet e tente de novo.';
  }
  return message
    ? `Não foi possível concluir agora (${message}).`
    : 'Não foi possível concluir agora. Tente de novo.';
}

/** Raised when the database refuses the reader (not an administrator). */
export class PainelAccessError extends Error {
  constructor() {
    super('Sua conta não tem acesso ao painel.');
    this.name = 'PainelAccessError';
  }
}

// ---------------------------------------------------------------------------
// Rows
// ---------------------------------------------------------------------------

export interface DailyActivity {
  day: string;
  installations: number;
  app_opens: number;
  chat_sessions: number;
  errors: number;
  events: number;
}

export interface DailyUsage {
  day: string;
  turns: number;
  tokens_in: number;
  tokens_out: number;
  tool_calls: number;
  latency_ms_p50: number | null;
  latency_ms_p95: number | null;
  duration_ms: number;
}

export interface FeatureUsage {
  feature: string;
  uses: number;
  installations: number;
  last_used_at: string | null;
}

export interface ErrorClass {
  error_class: string;
  occurrences: number;
  installations: number;
  last_seen_at: string | null;
}

export interface PlatformRow {
  platform: string;
  os: string;
  app_version: string;
  installations: number;
  last_seen_at: string | null;
}

export interface InstallFunnel {
  install_started: number;
  install_completed: number;
  setup_completed: number;
  first_chat_sent: number;
  active_chatters: number;
}

export interface ConsentRow {
  granted: boolean | null;
  policy_version: string | null;
  records: number;
  last_at: string | null;
}

export interface EventRow {
  id: number;
  received_at: string;
  anon_id: string;
  event: string;
  properties: Record<string, unknown>;
  app_version: string | null;
  platform: string | null;
  os: string | null;
}

export interface PainelData {
  period: Period;
  /** Last day of the period (today in São Paulo), YYYY-MM-DD. */
  today: string;
  activity: DailyActivity[];
  usage: DailyUsage[];
  /** Distinct installations in the period and in the same span before it. */
  activeInstallations: { current: number; previous: number } | null;
  /** Feature use and error classes within the period. */
  features: FeatureUsage[];
  errorClasses: ErrorClass[];
  platforms: PlatformRow[];
  funnel: InstallFunnel | null;
  consent: ConsentRow[];
  recent: EventRow[];
}

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};
const numOrNull = (v: unknown): number | null => (v === null || v === undefined ? null : num(v));
const str = (v: unknown, fallback = ''): string => (typeof v === 'string' ? v : fallback);
const strOrNull = (v: unknown): string | null => (typeof v === 'string' ? v : null);
type Raw = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Dates (the views bucket days in America/Sao_Paulo)
// ---------------------------------------------------------------------------

export function todayInSaoPaulo(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Sao_Paulo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

export function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** The `period` days ending at `today`, oldest first. */
export function daysOf(period: number, today: string): string[] {
  return Array.from({ length: period }, (_, i) => addDays(today, i - period + 1));
}

// ---------------------------------------------------------------------------
// Fetching
// ---------------------------------------------------------------------------

interface QueryResult {
  data: unknown;
  error: { code?: string; message?: string } | null;
}

function rowsOf(result: QueryResult): Raw[] {
  if (result.error) {
    if (result.error.code === '42501') throw new PainelAccessError();
    throw new Error(painelErrorMessage(result.error));
  }
  return Array.isArray(result.data) ? (result.data as Raw[]) : [];
}

/** Unpack `nicx_period_summary` (a JSON object), tolerating a missing result. */
function summaryOf(result: QueryResult): {
  installations: { current: number; previous: number } | null;
  features: Raw[];
  errorClasses: Raw[];
} {
  if (result.error) {
    if (result.error.code === '42501') throw new PainelAccessError();
    throw new Error(painelErrorMessage(result.error));
  }
  const raw = result.data && typeof result.data === 'object' ? (result.data as Raw) : null;
  const list = (v: unknown): Raw[] => (Array.isArray(v) ? (v as Raw[]) : []);
  return {
    installations: raw
      ? { current: num(raw.installations), previous: num(raw.installations_prev) }
      : null,
    features: list(raw?.features),
    errorClasses: list(raw?.error_classes),
  };
}

/** Whether the signed-in user is a Falkyria administrator. */
export async function checkIsAdmin(client: SupabaseClient): Promise<boolean> {
  const { data, error } = await client.rpc('nicx_is_admin');
  if (error) throw new Error(painelErrorMessage(error));
  return data === true;
}

/**
 * Load everything the dashboard shows. Daily views cover twice the period
 * so the KPI tiles can compare with the period before.
 */
export async function fetchPainelData(
  client: SupabaseClient,
  period: Period,
  today: string = todayInSaoPaulo(),
): Promise<PainelData> {
  const since = addDays(today, -(2 * period - 1));
  const [activity, usage, summary, platforms, funnel, consent, recent] =
    await Promise.all([
      client.from('nicx_daily_activity').select('*').gte('day', since).order('day'),
      client.from('nicx_daily_usage').select('*').gte('day', since).order('day'),
      client.rpc('nicx_period_summary', { p_days: period }),
      client.from('nicx_platforms').select('*').order('installations', { ascending: false }),
      client.from('nicx_install_funnel').select('*'),
      client.from('nicx_consent_summary').select('*'),
      client
        .from('nicx_events')
        .select('id,received_at,anon_id,event,properties,app_version,platform,os')
        .order('received_at', { ascending: false })
        .limit(50),
    ]);

  const funnelRow = rowsOf(funnel)[0];
  const periodSummary = summaryOf(summary);
  return {
    period,
    today,
    activity: rowsOf(activity).map((r) => ({
      day: str(r.day),
      installations: num(r.installations),
      app_opens: num(r.app_opens),
      chat_sessions: num(r.chat_sessions),
      errors: num(r.errors),
      events: num(r.events),
    })),
    usage: rowsOf(usage).map((r) => ({
      day: str(r.day),
      turns: num(r.turns),
      tokens_in: num(r.tokens_in),
      tokens_out: num(r.tokens_out),
      tool_calls: num(r.tool_calls),
      latency_ms_p50: numOrNull(r.latency_ms_p50),
      latency_ms_p95: numOrNull(r.latency_ms_p95),
      duration_ms: num(r.duration_ms),
    })),
    activeInstallations: periodSummary.installations,
    features: periodSummary.features.map((r) => ({
      feature: str(r.feature, 'desconhecido'),
      uses: num(r.uses),
      installations: num(r.installations),
      last_used_at: strOrNull(r.last_used_at),
    })),
    errorClasses: periodSummary.errorClasses.map((r) => ({
      error_class: str(r.error_class, 'unknown_error'),
      occurrences: num(r.occurrences),
      installations: num(r.installations),
      last_seen_at: strOrNull(r.last_seen_at),
    })),
    platforms: rowsOf(platforms).map((r) => ({
      platform: str(r.platform, 'desconhecida'),
      os: str(r.os, 'desconhecido'),
      app_version: str(r.app_version, 'desconhecida'),
      installations: num(r.installations),
      last_seen_at: strOrNull(r.last_seen_at),
    })),
    funnel: funnelRow
      ? {
          install_started: num(funnelRow.install_started),
          install_completed: num(funnelRow.install_completed),
          setup_completed: num(funnelRow.setup_completed),
          first_chat_sent: num(funnelRow.first_chat_sent),
          active_chatters: num(funnelRow.active_chatters),
        }
      : null,
    consent: rowsOf(consent).map((r) => ({
      granted: typeof r.granted === 'boolean' ? r.granted : null,
      policy_version: strOrNull(r.policy_version),
      records: num(r.records),
      last_at: strOrNull(r.last_at),
    })),
    recent: rowsOf(recent).map((r) => ({
      id: num(r.id),
      received_at: str(r.received_at),
      anon_id: str(r.anon_id),
      event: str(r.event),
      properties:
        r.properties && typeof r.properties === 'object' && !Array.isArray(r.properties)
          ? (r.properties as Record<string, unknown>)
          : {},
      app_version: strOrNull(r.app_version),
      platform: strOrNull(r.platform),
      os: strOrNull(r.os),
    })),
  };
}

// ---------------------------------------------------------------------------
// Shaping for the charts and tiles
// ---------------------------------------------------------------------------

export interface DayPoint {
  day: string;
  installations: number;
  chat_sessions: number;
  errors: number;
  tokens_in: number;
  tokens_out: number;
}

/** One point per day of the period, with zeros for days without events. */
export function dailySeries(data: PainelData): DayPoint[] {
  const activity = new Map(data.activity.map((r) => [r.day, r]));
  const usage = new Map(data.usage.map((r) => [r.day, r]));
  return daysOf(data.period, data.today).map((day) => ({
    day,
    installations: activity.get(day)?.installations ?? 0,
    chat_sessions: activity.get(day)?.chat_sessions ?? 0,
    errors: activity.get(day)?.errors ?? 0,
    tokens_in: usage.get(day)?.tokens_in ?? 0,
    tokens_out: usage.get(day)?.tokens_out ?? 0,
  }));
}

export interface Kpi {
  current: number;
  previous: number;
}

export interface Kpis {
  /** Distinct installations in the period (average per day if unavailable). */
  installations: Kpi;
  chatSessions: Kpi;
  tokens: Kpi;
  errors: Kpi;
}

/** Totals for the period and for the same span right before it. */
export function computeKpis(data: PainelData): Kpis {
  const current = new Set(daysOf(data.period, data.today));
  const previous = new Set(daysOf(data.period, addDays(data.today, -data.period)));
  const sum = <T extends { day: string }>(rows: T[], days: Set<string>, pick: (r: T) => number) =>
    rows.reduce((acc, r) => (days.has(r.day) ? acc + pick(r) : acc), 0);
  const both = <T extends { day: string }>(rows: T[], pick: (r: T) => number): Kpi => ({
    current: sum(rows, current, pick),
    previous: sum(rows, previous, pick),
  });
  const installs = both(data.activity, (r) => r.installations);
  return {
    installations: data.activeInstallations ?? {
      current: installs.current / data.period,
      previous: installs.previous / data.period,
    },
    chatSessions: both(data.activity, (r) => r.chat_sessions),
    tokens: both(data.usage, (r) => r.tokens_in + r.tokens_out),
    errors: both(data.activity, (r) => r.errors),
  };
}

/** Relative change, or null when there is no previous value to compare. */
export function relativeChange({ current, previous }: Kpi): number | null {
  if (previous === 0) return null;
  return (current - previous) / previous;
}

export function isEmpty(data: PainelData): boolean {
  return (
    data.activity.length === 0 &&
    data.usage.length === 0 &&
    data.features.length === 0 &&
    data.errorClasses.length === 0 &&
    data.platforms.length === 0 &&
    data.consent.length === 0 &&
    data.recent.length === 0 &&
    (!data.funnel || Object.values(data.funnel).every((v) => v === 0))
  );
}

// ---------------------------------------------------------------------------
// Labels in Portuguese
// ---------------------------------------------------------------------------

export const FEATURE_LABELS: Record<string, string> = {
  chat: 'Chat',
  voice: 'Voz',
  agents: 'Agentes',
  skills: 'Habilidades',
  memory: 'Memória',
  tools: 'Ferramentas',
  connectors: 'Conectores',
  scheduler: 'Agendador',
  workflows: 'Fluxos de trabalho',
  digest: 'Resumo diário',
  research: 'Pesquisa',
  evals: 'Avaliações',
  feedback: 'Feedback',
  telemetry_dashboard: 'Painel de telemetria',
  settings: 'Configurações',
  overlay: 'Janela flutuante',
};

export const ERROR_LABELS: Record<string, string> = {
  network_error: 'Rede',
  engine_unreachable: 'Motor de IA fora do ar',
  model_not_found: 'Modelo não encontrado',
  tool_timeout: 'Ferramenta demorou demais',
  tool_error: 'Erro em ferramenta',
  rate_limit: 'Limite de requisições',
  auth_failure: 'Falha de autenticação',
  permission_denied: 'Permissão negada',
  validation_error: 'Dados inválidos',
  config_error: 'Configuração',
  unknown_error: 'Desconhecido',
};

export const EVENT_LABELS: Record<string, string> = {
  install_started: 'Instalação iniciada',
  install_stage_completed: 'Etapa de instalação',
  install_completed: 'Instalação concluída',
  install_failed: 'Instalação falhou',
  uninstall_started: 'Desinstalação',
  app_opened: 'App aberto',
  setup_completed: 'Configuração concluída',
  first_chat_sent: 'Primeira conversa',
  chat_session_ended: 'Sessão de chat',
  tool_first_used: 'Primeira ferramenta',
  model_changed: 'Troca de modelo',
  connector_auth_completed: 'Conector autorizado',
  feature_used: 'Recurso usado',
  feedback_submitted: 'Feedback',
  error_shown_to_user: 'Erro exibido',
  settings_changed: 'Configuração alterada',
  usage_daily_summary: 'Resumo diário',
  analytics_consent: 'Consentimento',
};

export const FUNNEL_STEPS: { key: keyof InstallFunnel; label: string }[] = [
  { key: 'install_started', label: 'Instalação iniciada' },
  { key: 'install_completed', label: 'Instalação concluída' },
  { key: 'setup_completed', label: 'Configuração concluída' },
  { key: 'first_chat_sent', label: 'Primeira conversa' },
  { key: 'active_chatters', label: 'Usam o chat' },
];
