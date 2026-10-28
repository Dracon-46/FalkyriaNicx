/**
 * Frontend analytics client.
 *
 * Nicx sends anonymous usage events to Falkyria only with the user's
 * consent (LGPD). The frontend never talks to the analytics destination
 * itself: every event goes through the local server
 * (POST /v1/analytics/capture), which applies the same catalog and
 * redaction rules as backend events and silently drops anything sent
 * without consent.
 *
 *   - The identity (consent state, anonymous ID) comes from
 *     GET /v1/analytics/identity and is cached in a small zustand store so
 *     the consent dialog and the privacy settings stay in sync.
 *   - track() is fire-and-forget: it posts only when the identity says
 *     `enabled`, and never throws or blocks the UI.
 *   - The consent, deletion and legal-text endpoints live here too, so all
 *     analytics traffic has one owner.
 */

import { create } from 'zustand';
import { apiFetch } from './api';
import i18n from '../i18n';

/**
 * Mirror of the Python event catalog (src/nicx/privacidade/events.py
 * REGISTRY). Anything not in this set is dropped with a console.warn at
 * track() time, so typos surface in development. `analytics_consent` is
 * missing on purpose: the server records it when the user makes a choice.
 *
 * KEEP IN SYNC with the Python REGISTRY.
 */
const KNOWN_EVENTS = new Set<string>([
  'install_started',
  'install_stage_completed',
  'install_completed',
  'install_failed',
  'uninstall_started',
  'app_opened',
  'setup_completed',
  'first_chat_sent',
  'chat_session_ended',
  'tool_first_used',
  'model_changed',
  'connector_auth_completed',
  'feature_used',
  'feedback_submitted',
  'error_shown_to_user',
  'settings_changed',
  'usage_daily_summary',
]);

// Hardcoded app version — the server also stamps its own version on every
// event, so this only fills the `version` property of `app_opened`.
const APP_VERSION = '1.0.1';

export interface AnalyticsIdentity {
  /** True only with consent and a configured destination. */
  enabled: boolean;
  anon_id: string;
  host: string;
  key: string;
  /** False until the user answers the consent dialog (or the CLI prompt). */
  choice_recorded: boolean;
  /** Version of the privacy policy the choice refers to. */
  policy_version: string;
}

export type LegalDocument = 'privacidade' | 'termos' | 'consentimento';

export interface ForgetResult {
  removed: number;
  anon_id: string;
}

interface AnalyticsState {
  identity: AnalyticsIdentity | null;
}

/** The last identity the server reported (null until the first load). */
export const useAnalyticsIdentity = create<AnalyticsState>(() => ({ identity: null }));

let pendingIdentity: Promise<AnalyticsIdentity | null> | null = null;
let identityAttempt = 0;

function normalizeIdentity(raw: Partial<AnalyticsIdentity> | null | undefined): AnalyticsIdentity {
  return {
    enabled: raw?.enabled === true,
    anon_id: typeof raw?.anon_id === 'string' ? raw.anon_id : '',
    host: typeof raw?.host === 'string' ? raw.host : '',
    key: typeof raw?.key === 'string' ? raw.key : '',
    choice_recorded: raw?.choice_recorded === true,
    policy_version: typeof raw?.policy_version === 'string' ? raw.policy_version : '',
  };
}

function storeIdentity(identity: AnalyticsIdentity, { supersede = false } = {}): AnalyticsIdentity {
  if (supersede) identityAttempt++;
  useAnalyticsIdentity.setState({ identity });
  pendingIdentity = Promise.resolve(identity);
  return identity;
}

/** Read the server's error `detail`, falling back to a fixed message. */
async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.detail === 'string' && body.detail.trim()) return body.detail;
  } catch {
    // Not JSON: keep the fallback.
  }
  return fallback;
}

/**
 * Load the analytics identity once and share the result. Resolves to null
 * when the server is unreachable; the next call then tries again.
 */
export function loadAnalyticsIdentity({ force = false } = {}): Promise<AnalyticsIdentity | null> {
  if (pendingIdentity && !force) return pendingIdentity;
  const attempt = ++identityAttempt;
  const request = (async (): Promise<AnalyticsIdentity | null> => {
    const response = await apiFetch('/v1/analytics/identity');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const identity = normalizeIdentity(await response.json());
    // A choice saved meanwhile is newer than this answer: keep it.
    if (attempt !== identityAttempt) return useAnalyticsIdentity.getState().identity ?? identity;
    return storeIdentity(identity);
  })().catch(() => {
    // Unreachable server: forget this attempt so the next call retries.
    if (attempt === identityAttempt) pendingIdentity = null;
    return null;
  });
  pendingIdentity = request;
  return request;
}

/** Fetch the identity in the background. Idempotent; never throws. */
export async function initAnalytics(): Promise<void> {
  await loadAnalyticsIdentity();
}

export function isAnalyticsEnabled(): boolean {
  return useAnalyticsIdentity.getState().identity?.enabled === true;
}

/** Record the user's choice. The server also logs it as proof of consent. */
export async function setAnalyticsPreference(enabled: boolean): Promise<AnalyticsIdentity> {
  let response: Response;
  try {
    response = await apiFetch('/v1/analytics/preference', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
  } catch {
    throw new Error(i18n.t('errors.privacy.serverUnreachable'));
  }
  if (!response.ok) {
    throw new Error(
      await errorDetail(response, i18n.t('errors.privacy.saveChoiceFailed')),
    );
  }
  return storeIdentity(normalizeIdentity(await response.json()), { supersede: true });
}

/**
 * Delete this installation's events from Falkyria's servers and start a new
 * anonymous ID (LGPD right to deletion).
 */
export async function forgetAnalyticsData(): Promise<ForgetResult> {
  let response: Response;
  try {
    response = await apiFetch('/v1/analytics/forget', { method: 'POST' });
  } catch {
    throw new Error(i18n.t('errors.privacy.serverUnreachable'));
  }
  if (!response.ok) {
    throw new Error(
      await errorDetail(response, i18n.t('errors.privacy.forgetFailed')),
    );
  }
  const body = await response.json();
  const result: ForgetResult = {
    removed: Number.isFinite(body?.removed) ? Number(body.removed) : 0,
    anon_id: typeof body?.anon_id === 'string' ? body.anon_id : '',
  };
  const current = useAnalyticsIdentity.getState().identity;
  if (current?.enabled) storeIdentity({ ...current, anon_id: result.anon_id }, { supersede: true });
  return result;
}

const legalCache = new Map<LegalDocument, string>();

/** Markdown text of a legal document bundled with the server. */
export async function fetchLegalDocument(name: LegalDocument): Promise<string> {
  const cached = legalCache.get(name);
  if (cached !== undefined) return cached;
  let response: Response;
  try {
    response = await apiFetch(`/v1/analytics/legal/${name}`);
  } catch {
    throw new Error(i18n.t('errors.privacy.documentUnreachable'));
  }
  if (!response.ok) {
    throw new Error(await errorDetail(response, i18n.t('errors.privacy.documentFailed')));
  }
  const text = await response.text();
  if (/^\s*</.test(text)) {
    throw new Error(i18n.t('errors.privacy.documentUnreachable'));
  }
  legalCache.set(name, text);
  return text;
}

/**
 * Send one event through the local server. Fire-and-forget: posts only
 * when the identity says analytics is enabled and never throws. Unknown
 * event names are dropped here so typos surface during development.
 */
export function track(event: string, properties: Record<string, unknown> = {}): void {
  if (!KNOWN_EVENTS.has(event)) {
    if (import.meta.env.DEV) {
      console.warn(
        `[analytics] Unknown event "${event}" dropped. ` +
          `Add it to KNOWN_EVENTS in lib/analytics.ts and to the Python ` +
          `REGISTRY in src/nicx/privacidade/events.py.`,
      );
    }
    return;
  }
  const known = useAnalyticsIdentity.getState().identity;
  if (known && !known.enabled) return;

  void (async () => {
    try {
      const identity = known ?? (await loadAnalyticsIdentity());
      if (!identity?.enabled) return;
      // The server keeps only the properties each event declares, so the
      // shared context below is dropped where it does not apply.
      await apiFetch('/v1/analytics/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event,
          properties: { version: APP_VERSION, platform: detectPlatform(), ...properties },
        }),
        keepalive: true,
      });
    } catch {
      // Analytics must never break the UI.
    }
  })();
}

/**
 * Hash an identifier to a 16-char sha256 hex prefix.
 *
 * Used for model / tool names that we want to cohort on without
 * actually shipping the raw value. Mirror of the backend's
 * :func:`nicx.privacidade.redaction.hash_id`.
 */
export async function hashId(s: string): Promise<string> {
  if (!s) return '';
  try {
    const data = new TextEncoder().encode(s);
    const buf = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(buf))
      .slice(0, 8)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  } catch {
    return '';
  }
}

/**
 * Detect platform string conforming to the events.py allowlist:
 * "tauri-macos" | "tauri-linux" | "tauri-windows" | "web".
 */
export function detectPlatform(): string {
  const ua =
    typeof navigator !== 'undefined' ? navigator.userAgent.toLowerCase() : '';
  const isTauri =
    typeof window !== 'undefined' &&
    !!(window as unknown as { __TAURI_INTERNALS__?: unknown })
      .__TAURI_INTERNALS__;
  if (isTauri) {
    if (ua.includes('mac')) return 'tauri-macos';
    if (ua.includes('windows')) return 'tauri-windows';
    return 'tauri-linux';
  }
  return 'web';
}
