// @vitest-environment happy-dom
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Markdown renders asynchronously; leave room for slow, busy machines.
configure({ asyncUtilTimeout: 5000 });

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock('../../lib/api', () => ({ apiFetch: mocks.apiFetch }));

const identity = (enabled: boolean) => ({
  enabled,
  anon_id: enabled ? '7c1e0b8e-0000-4000-8000-000000000001' : '',
  host: 'https://exemplo.supabase.co',
  key: enabled ? 'sb_publishable_teste' : '',
  choice_recorded: true,
  policy_version: '2026-10-23',
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function serve({ enabled = true, forget = () => json({ removed: 1234, anon_id: 'novo-id' }) } = {}) {
  let current = enabled;
  mocks.apiFetch.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/v1/analytics/identity') return json(identity(current));
    if (path === '/v1/analytics/preference') {
      current = JSON.parse(init!.body as string).enabled;
      return json(identity(current));
    }
    if (path === '/v1/analytics/forget') return forget();
    if (path === '/v1/analytics/legal/termos') return new Response('# Termos de Uso do Nicx\n\nTexto dos termos.');
    return new Response(null, { status: 204 });
  });
}

const calls = (path: string) => mocks.apiFetch.mock.calls.filter(([p]) => p === path);

async function renderSection() {
  const { PrivacySection } = await import('./PrivacySection');
  return render(<PrivacySection />);
}

beforeEach(() => {
  vi.resetModules();
  mocks.apiFetch.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('PrivacySection', () => {
  it('shows the current choice and the policy version, and saves a change', async () => {
    serve({ enabled: true });
    await renderSection();

    const toggle = await screen.findByRole('switch', { name: 'Enviar estatísticas anônimas de uso' });
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));
    expect(screen.getByText('Política de privacidade, versão 2026-10-23')).toBeTruthy();

    fireEvent.click(toggle);
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('false'));
    expect(JSON.parse(calls('/v1/analytics/preference')[0][1].body)).toEqual({ enabled: false });
  });

  it('asks for confirmation in the app before deleting, then reports how many events were removed', async () => {
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    serve();
    await renderSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Apagar meus dados' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Apagar seus dados de uso?' });
    expect(calls('/v1/analytics/forget')).toHaveLength(0);
    expect(confirmSpy).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Apagar dados' }));
    expect((await screen.findByRole('status')).textContent).toBe(
      '1.234 eventos apagados dos servidores da Falkyria.',
    );
    expect(calls('/v1/analytics/forget')).toHaveLength(1);
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
  });

  it('does nothing when the deletion is cancelled', async () => {
    serve();
    await renderSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Apagar meus dados' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }));

    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
    expect(calls('/v1/analytics/forget')).toHaveLength(0);
  });

  it('shows the server message when Falkyria cannot be reached (502)', async () => {
    serve({
      forget: () => json({ detail: 'Não foi possível apagar seus dados agora. Tente de novo.' }, 502),
    });
    await renderSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Apagar meus dados' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apagar dados' }));

    expect((await screen.findByRole('alert')).textContent).toBe(
      'Não foi possível apagar seus dados agora. Tente de novo.',
    );
  });

  it('opens the terms of use in a readable dialog', async () => {
    serve();
    await renderSection();

    fireEvent.click(await screen.findByRole('button', { name: 'Termos de uso' }));
    expect(await screen.findByRole('dialog', { name: 'Termos de Uso do Nicx' })).toBeTruthy();
    expect(await screen.findByText('Texto dos termos.')).toBeTruthy();
  });

  it('words the deletion result correctly for zero and one event', async () => {
    const { forgetMessage } = await import('./PrivacySection');
    expect(forgetMessage(0)).toBe('Nenhum evento desta instalação estava nos servidores da Falkyria.');
    expect(forgetMessage(1)).toBe('1 evento apagado dos servidores da Falkyria.');
  });
});
