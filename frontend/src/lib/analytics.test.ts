import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock('./api', () => ({ apiFetch: mocks.apiFetch }));

const identity = (enabled: boolean, extra: Record<string, unknown> = {}) => ({
  enabled,
  anon_id: enabled ? '7c1e0b8e-0000-4000-8000-000000000001' : '',
  host: 'https://exemplo.supabase.co',
  key: enabled ? 'sb_publishable_teste' : '',
  choice_recorded: true,
  policy_version: '2026-10-23',
  ...extra,
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** Requests sent to a given path, with their parsed JSON bodies. */
const callsTo = (path: string) =>
  mocks.apiFetch.mock.calls
    .filter(([p]) => p === path)
    .map(([, init]) => (init?.body ? JSON.parse(init.body as string) : undefined));

/** Let fire-and-forget promises settle. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function routeTo(identityBody: unknown) {
  mocks.apiFetch.mockImplementation(async (path: string) => {
    if (path === '/v1/analytics/identity') return json(identityBody);
    if (path === '/v1/analytics/capture') return new Response(null, { status: 204 });
    throw new Error(`unexpected ${path}`);
  });
}

beforeEach(() => {
  vi.resetModules();
  mocks.apiFetch.mockReset();
});

describe('analytics', () => {
  it('never posts events when the user has not consented', async () => {
    routeTo(identity(false));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    analytics.track('app_opened');
    await settle();
    expect(callsTo('/v1/analytics/capture')).toHaveLength(0);
    expect(analytics.isAnalyticsEnabled()).toBe(false);
  });

  it('loads the identity once and posts known events through the local server', async () => {
    routeTo(identity(true));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    await analytics.initAnalytics();
    expect(callsTo('/v1/analytics/identity')).toHaveLength(1);
    expect(analytics.isAnalyticsEnabled()).toBe(true);

    analytics.track('feature_used', { feature_name: 'voice' });
    await settle();
    const [body] = callsTo('/v1/analytics/capture');
    expect(body.event).toBe('feature_used');
    expect(body.properties).toMatchObject({ feature_name: 'voice', platform: 'web' });
    const init = mocks.apiFetch.mock.calls.find(([p]) => p === '/v1/analytics/capture')![1];
    expect(init.method).toBe('POST');
    expect(init.keepalive).toBe(true);
  });

  it('waits for the identity when an event is tracked before init finishes', async () => {
    routeTo(identity(true));
    const analytics = await import('./analytics');
    analytics.track('app_opened');
    await settle();
    await settle();
    expect(callsTo('/v1/analytics/capture')).toHaveLength(1);
  });

  it('drops unknown events', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    routeTo(identity(true));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    analytics.track('not_a_real_event');
    await settle();
    expect(callsTo('/v1/analytics/capture')).toHaveLength(0);
    warn.mockRestore();
  });

  it('stays off silently when the server is unreachable, and never throws from track', async () => {
    mocks.apiFetch.mockRejectedValue(new TypeError('Failed to fetch'));
    const analytics = await import('./analytics');
    await expect(analytics.initAnalytics()).resolves.toBeUndefined();
    expect(() => analytics.track('app_opened')).not.toThrow();
    await settle();
    expect(analytics.isAnalyticsEnabled()).toBe(false);
    expect(callsTo('/v1/analytics/capture')).toHaveLength(0);
  });

  it('starts and stops sending as soon as the preference changes', async () => {
    routeTo(identity(false, { choice_recorded: false }));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();

    mocks.apiFetch.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/v1/analytics/preference') {
        const { enabled } = JSON.parse(init!.body as string);
        return json(identity(enabled));
      }
      return new Response(null, { status: 204 });
    });

    const granted = await analytics.setAnalyticsPreference(true);
    expect(granted.enabled).toBe(true);
    expect(analytics.useAnalyticsIdentity.getState().identity?.choice_recorded).toBe(true);
    analytics.track('app_opened');
    await settle();
    expect(callsTo('/v1/analytics/capture')).toHaveLength(1);

    await analytics.setAnalyticsPreference(false);
    analytics.track('app_opened');
    await settle();
    expect(callsTo('/v1/analytics/capture')).toHaveLength(1);
    expect(callsTo('/v1/analytics/preference')).toEqual([{ enabled: true }, { enabled: false }]);
  });

  it('surfaces the server message when deleting data fails', async () => {
    mocks.apiFetch.mockResolvedValue(
      json({ detail: 'Não foi possível apagar seus dados agora. Tente de novo.' }, 502),
    );
    const analytics = await import('./analytics');
    await expect(analytics.forgetAnalyticsData()).rejects.toThrow(
      'Não foi possível apagar seus dados agora. Tente de novo.',
    );
  });

  it('hashes identifiers to a 16-char hex prefix', async () => {
    const analytics = await import('./analytics');
    const hash = await analytics.hashId('qwen3.5:4b');
    expect(hash).toMatch(/^[0-9a-f]{16}$/);
    expect(await analytics.hashId('')).toBe('');
  });
});
