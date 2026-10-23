// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  createClient: vi.fn(),
}));
vi.mock('../lib/api', () => ({ apiFetch: mocks.apiFetch }));
vi.mock('@supabase/supabase-js', () => ({ createClient: mocks.createClient }));

const SESSION = { user: { id: 'u1', email: 'pessoa@falkyria.com.br' }, access_token: 't' };

function fakeClient({ session = null as unknown, isAdmin = false } = {}) {
  return {
    auth: {
      getSession: vi.fn(async () => ({ data: { session }, error: null })),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signInWithPassword: vi.fn(async () => ({
        data: {},
        error: { name: 'AuthApiError', status: 400, code: 'email_not_confirmed', message: 'Email not confirmed' },
      })),
      signUp: vi.fn(async () => ({ data: { user: {} }, error: null })),
      signOut: vi.fn(async () => ({ error: null })),
    },
    rpc: vi.fn(async () => ({ data: isAdmin, error: null })),
    from: vi.fn(),
  };
}

beforeEach(() => {
  vi.resetModules();
  mocks.apiFetch.mockReset();
  mocks.createClient.mockReset();
  mocks.apiFetch.mockImplementation(async (path: string) => {
    if (path === '/v1/analytics/dashboard-config') {
      return new Response(
        JSON.stringify({
          supabase_url: 'https://exemplo.supabase.co',
          supabase_key: 'sb_publishable_teste',
          policy_version: '2026-10-23',
        }),
        { headers: { 'Content-Type': 'application/json' } },
      );
    }
    return new Response(null, { status: 404 });
  });
});
afterEach(() => cleanup());

async function renderPage() {
  const { PainelPage } = await import('./PainelPage');
  return render(<PainelPage />);
}

describe('PainelPage', () => {
  it('shows the sign-in form when nobody is signed in', async () => {
    const client = fakeClient();
    mocks.createClient.mockReturnValue(client);
    await renderPage();

    expect(await screen.findByRole('heading', { name: 'Painel Falkyria' })).toBeTruthy();
    expect(screen.getByLabelText('E-mail')).toBeTruthy();
    expect(screen.getByLabelText('Senha')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeTruthy();
    expect(mocks.createClient).toHaveBeenCalledWith(
      'https://exemplo.supabase.co',
      'sb_publishable_teste',
      expect.objectContaining({ auth: expect.objectContaining({ persistSession: true }) }),
    );
    expect(client.rpc).not.toHaveBeenCalled();
  });

  it('explains Supabase errors in Portuguese', async () => {
    const client = fakeClient();
    mocks.createClient.mockReturnValue(client);
    await renderPage();

    fireEvent.change(await screen.findByLabelText('E-mail'), { target: { value: 'pessoa@falkyria.com.br' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'uma-senha-longa' } });
    fireEvent.submit(screen.getByRole('button', { name: 'Entrar' }).closest('form')!);

    expect((await screen.findByRole('alert')).textContent).toContain('E-mail ainda não confirmado');
  });

  it('tells new accounts that a confirmation email is on its way', async () => {
    const client = fakeClient();
    mocks.createClient.mockReturnValue(client);
    await renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Criar conta' }));
    expect(screen.getByText(/receber um e-mail de confirmação/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'nova@falkyria.com.br' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'senha-bem-longa-123' } });
    fireEvent.submit(screen.getByLabelText('Senha').closest('form')!);

    expect((await screen.findByRole('status')).textContent).toContain('nova@falkyria.com.br');
    expect(client.auth.signUp).toHaveBeenCalledWith({
      email: 'nova@falkyria.com.br',
      password: 'senha-bem-longa-123',
    });
  });

  it('shows the no-access message when the account is not a Falkyria administrator', async () => {
    const client = fakeClient({ session: SESSION, isAdmin: false });
    mocks.createClient.mockReturnValue(client);
    await renderPage();

    expect(
      await screen.findByText('Sua conta não tem acesso ao painel. Peça a um administrador da Falkyria.'),
    ).toBeTruthy();
    expect(client.rpc).toHaveBeenCalledWith('nicx_is_admin');
    expect(client.from).not.toHaveBeenCalled();
    expect(screen.getByText('Conectado como pessoa@falkyria.com.br')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    await waitFor(() => expect(client.auth.signOut).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeTruthy();
  });

  it('explains when the local server cannot provide the dashboard settings', async () => {
    mocks.apiFetch.mockRejectedValue(new TypeError('Failed to fetch'));
    await renderPage();

    expect(await screen.findByText('Não foi possível falar com o servidor do Nicx.')).toBeTruthy();
    expect(mocks.createClient).not.toHaveBeenCalled();
  });
});
