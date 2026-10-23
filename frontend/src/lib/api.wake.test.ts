// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __resetWakeSupportForTests,
  fetchWakeStatus,
  reportVoiceBusy,
  WakeUnsupportedError,
} from './api';

const fetchMock = vi.fn<typeof fetch>();

function reply(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('"Nicx, ligar" on a server without the wake routes', () => {
  beforeEach(() => {
    __resetWakeSupportForTests();
    fetchMock.mockReset();
    globalThis.fetch = fetchMock;
  });

  it('reports the missing route once and then stops asking', async () => {
    fetchMock.mockResolvedValue(reply(404, { detail: 'Not Found' }));

    await expect(fetchWakeStatus()).rejects.toBeInstanceOf(WakeUnsupportedError);
    await expect(fetchWakeStatus()).rejects.toBeInstanceOf(WakeUnsupportedError);
    await reportVoiceBusy('aba', true);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('a 404 on the busy flag silences later reports too', async () => {
    fetchMock.mockResolvedValue(reply(404));
    await reportVoiceBusy('aba', true);
    await reportVoiceBusy('aba', true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('works normally on a current server', async () => {
    fetchMock.mockImplementation(async () => reply(200, { enabled: false, running: false }));
    await expect(fetchWakeStatus()).resolves.toMatchObject({ enabled: false });
    await reportVoiceBusy('aba', true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
