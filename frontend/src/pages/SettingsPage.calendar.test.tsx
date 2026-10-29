// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchCalendarConfig: vi.fn(),
  updateCalendarConfig: vi.fn(),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api')>()),
  ...api,
}));

import { CalendarSettings } from '../components/Settings/CalendarSettings';

const base = {
  calendario_padrao: 'windows',
  opcoes: ['windows', 'google', 'outlook', 'outlook_trabalho'],
  google_conectado: true,
  google_escrita: false,
  outlook_conectado: false,
  outlook_escrita: false,
};

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('CalendarSettings', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('mostra o padrão, as contas e salva a troca', async () => {
    api.fetchCalendarConfig.mockResolvedValue(base);
    api.updateCalendarConfig.mockResolvedValue({ ...base, calendario_padrao: 'google' });
    const onSaved = vi.fn();
    render(<CalendarSettings onSaved={onSaved} />);

    const select = (await screen.findByTestId('calendar-default')) as HTMLSelectElement;
    await waitFor(() => expect(select.disabled).toBe(false));
    expect(select.value).toBe('windows');
    expect(screen.getByText(/só leitura; reconecte/)).toBeTruthy();
    expect(screen.getByText(/Outlook: sem conta com permissão de agenda/)).toBeTruthy();

    fireEvent.change(select, { target: { value: 'google' } });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.updateCalendarConfig).toHaveBeenCalledWith('google');
    expect(select.value).toBe('google');
  });
});
