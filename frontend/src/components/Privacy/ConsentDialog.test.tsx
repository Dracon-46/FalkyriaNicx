// @vitest-environment happy-dom
import { act, cleanup, configure, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Markdown renders asynchronously; leave room for slow, busy machines.
configure({ asyncUtilTimeout: 5000 });

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock('../../lib/api', () => ({ apiFetch: mocks.apiFetch }));

const CONSENT_MD =
  '## Ajude a melhorar o Nicx\n\nCom a sua permissão, o Nicx envia **estatísticas anônimas de uso**.';
const POLICY_MD = '# Política de Privacidade do Nicx\n\n**Versão 2026-10-23**\n\nSuas conversas ficam no seu computador.';

const identity = (enabled: boolean, choice_recorded: boolean) => ({
  enabled,
  anon_id: enabled ? '7c1e0b8e-0000-4000-8000-000000000001' : '',
  host: 'https://exemplo.supabase.co',
  key: enabled ? 'sb_publishable_teste' : '',
  choice_recorded,
  policy_version: '2026-10-23',
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function serve({ recorded = false, preferenceStatus = 200 } = {}) {
  mocks.apiFetch.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/v1/analytics/identity') return json(identity(false, recorded));
    if (path === '/v1/analytics/legal/consentimento') return new Response(CONSENT_MD);
    if (path === '/v1/analytics/legal/privacidade') return new Response(POLICY_MD);
    if (path === '/v1/analytics/preference') {
      if (preferenceStatus !== 200) return json({ detail: 'Falha ao salvar.' }, preferenceStatus);
      const { enabled } = JSON.parse(init!.body as string);
      return json(identity(enabled, true));
    }
    return new Response(null, { status: 204 });
  });
}

const preferenceBodies = () =>
  mocks.apiFetch.mock.calls
    .filter(([p]) => p === '/v1/analytics/preference')
    .map(([, init]) => JSON.parse(init.body));

async function renderGate() {
  const { ConsentGate } = await import('./ConsentDialog');
  return render(<ConsentGate />);
}

beforeEach(() => {
  vi.resetModules();
  mocks.apiFetch.mockReset();
});
afterEach(() => cleanup());

describe('ConsentGate', () => {
  it('asks on first launch with the consent text and two equal answers', async () => {
    serve();
    await renderGate();

    const dialog = await screen.findByRole('dialog', { name: 'Ajude a melhorar o Nicx' });
    expect(await screen.findByText('estatísticas anônimas de uso')).toBeTruthy();
    const accept = screen.getByRole('button', { name: 'Aceitar' });
    const decline = screen.getByRole('button', { name: 'Agora não' });
    // Same look for both answers: no dark patterns.
    expect(accept.className).toBe(decline.className);
    expect(accept.getAttribute('style')).toBe(decline.getAttribute('style'));
    expect(dialog.querySelector('svg[aria-hidden="true"]')).toBeTruthy();
    expect(preferenceBodies()).toEqual([]);
  });

  it('records "Aceitar" and closes', async () => {
    serve();
    await renderGate();
    fireEvent.click(await screen.findByRole('button', { name: 'Aceitar' }));

    await waitFor(() => expect(preferenceBodies()).toEqual([{ enabled: true }]));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('treats Esc as "Agora não"', async () => {
    serve();
    await renderGate();
    const dialog = await screen.findByRole('dialog');
    await act(async () => {
      fireEvent.keyDown(dialog, { key: 'Escape' });
    });

    await waitFor(() => expect(preferenceBodies()).toEqual([{ enabled: false }]));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('opens the privacy policy on top of the question', async () => {
    serve();
    await renderGate();
    fireEvent.click(await screen.findByRole('button', { name: 'Ler a política de privacidade' }));

    expect(
      await screen.findByRole('dialog', { name: 'Política de Privacidade do Nicx' }),
    ).toBeTruthy();
    expect(await screen.findByText('Suas conversas ficam no seu computador.')).toBeTruthy();
    expect(preferenceBodies()).toEqual([]);
  });

  it('keeps the question open with the reason when saving consent fails', async () => {
    serve({ preferenceStatus: 500 });
    await renderGate();
    fireEvent.click(await screen.findByRole('button', { name: 'Aceitar' }));

    expect((await screen.findByRole('alert')).textContent).toBe('Falha ao salvar.');
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('never asks again once a choice is recorded', async () => {
    serve({ recorded: true });
    await renderGate();
    await waitFor(() =>
      expect(mocks.apiFetch).toHaveBeenCalledWith('/v1/analytics/identity'),
    );
    await act(async () => {});
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
