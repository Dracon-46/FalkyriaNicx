import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  init: vi.fn(),
  capture: vi.fn(),
  identify: vi.fn(),
  register: vi.fn(),
  opt_in_capturing: vi.fn(),
}));
vi.mock('./api', () => ({ apiFetch: mocks.apiFetch }));
vi.mock('posthog-js', () => ({
  default: {
    init: mocks.init,
    capture: mocks.capture,
    identify: mocks.identify,
    register: mocks.register,
    opt_in_capturing: mocks.opt_in_capturing,
  },
}));

const identity = (enabled: boolean, host = 'https://analytics.example.org') => ({
  enabled, key: enabled ? 'test-key' : '', anon_id: enabled ? 'test-id' : '', host,
});
const response = (enabled: boolean, host?: string) => ({
  ok: true, json: async () => identity(enabled, host),
});

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  mocks.init.mockImplementation((_key, config) => config.loaded(mocks));
});

describe('analytics', () => {
  it('does not initialize or send when the backend reports analytics off', async () => {
    mocks.apiFetch.mockResolvedValue(response(false));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    analytics.track('app_opened');
    expect(mocks.init).not.toHaveBeenCalled();
    expect(mocks.capture).not.toHaveBeenCalled();
    expect(analytics.isAnalyticsEnabled()).toBe(false);
  });

  it('does not initialize when no destination host is configured', async () => {
    mocks.apiFetch.mockResolvedValue(response(true, ''));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    analytics.track('app_opened');
    expect(mocks.init).not.toHaveBeenCalled();
    expect(mocks.capture).not.toHaveBeenCalled();
  });

  it('initializes once and captures known events when the backend enables it', async () => {
    mocks.apiFetch.mockResolvedValue(response(true));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    await analytics.initAnalytics();
    expect(mocks.apiFetch).toHaveBeenCalledOnce();
    expect(mocks.init).toHaveBeenCalledOnce();
    expect(mocks.opt_in_capturing).toHaveBeenCalledWith({ captureEventName: false });
    expect(analytics.isAnalyticsEnabled()).toBe(true);
    expect(analytics.getAnonId()).toBe('test-id');
    analytics.track('app_opened');
    expect(mocks.capture).toHaveBeenCalledWith('app_opened', {});
  });

  it('drops unknown events', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mocks.apiFetch.mockResolvedValue(response(true));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    analytics.track('not_a_real_event');
    expect(mocks.capture).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it('stays off silently when the identity request fails', async () => {
    mocks.apiFetch.mockResolvedValue({ ok: false });
    const analytics = await import('./analytics');
    await expect(analytics.initAnalytics()).resolves.toBeUndefined();
    expect(mocks.init).not.toHaveBeenCalled();
    expect(analytics.isAnalyticsEnabled()).toBe(false);
  });
});
