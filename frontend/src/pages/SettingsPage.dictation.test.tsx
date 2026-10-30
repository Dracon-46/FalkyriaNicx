// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchDictation: vi.fn(),
  updateDictation: vi.fn(),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api')>()),
  ...api,
}));

import { DictationSettings } from '../components/Settings/DictationSettings';
import { isDictating } from '../lib/dictation';

const base = {
  ativo: false,
  teclas: 'ctrl+alt+d',
  rotulo: 'Ctrl + Alt + D',
  modo: 'alternar',
  idioma: '',
  som: true,
  modos: ['alternar', 'segurar'],
  idiomas: ['pt-BR', 'en', 'es', 'zh', 'hi', 'ar', 'fr'],
  estado: 'desligado',
  mensagem: '',
  suportado: true,
};

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('DictationSettings', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('mostra a configuração e liga o ditado', async () => {
    api.fetchDictation.mockResolvedValue(base);
    api.updateDictation.mockResolvedValue({ ...base, ativo: true, estado: 'pronto' });
    const onSaved = vi.fn();
    render(<DictationSettings onSaved={onSaved} />);

    const toggle = await screen.findByRole('switch', { name: 'Ativar o ditado' });
    await waitFor(() => expect((toggle as HTMLButtonElement).disabled).toBe(false));
    expect(screen.getByTestId('dictation-recorder').textContent).toBe('Ctrl + Alt + D');
    expect(screen.getByTestId('dictation-state').textContent).toBe('Desligado');
    expect((screen.getByTestId('dictation-language') as HTMLSelectElement).value).toBe('');
    expect(screen.getByText(/"nova linha"/)).toBeTruthy();

    fireEvent.click(toggle);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.updateDictation).toHaveBeenCalledWith({ ativo: true });
    expect(screen.getByTestId('dictation-state').textContent).toBe('Pronto');
  });

  it('salva modo, idioma, som e uma combinação nova', async () => {
    api.fetchDictation.mockResolvedValue({ ...base, ativo: true, estado: 'pronto' });
    api.updateDictation.mockImplementation(async (change) => ({ ...base, ativo: true, estado: 'pronto', ...change }));
    render(<DictationSettings onSaved={() => {}} />);

    const mode = (await screen.findByTestId('dictation-mode')) as HTMLSelectElement;
    await waitFor(() => expect(mode.disabled).toBe(false));
    fireEvent.change(mode, { target: { value: 'segurar' } });
    await waitFor(() => expect(api.updateDictation).toHaveBeenCalledWith({ modo: 'segurar' }));

    fireEvent.change(screen.getByTestId('dictation-language'), { target: { value: 'en' } });
    await waitFor(() => expect(api.updateDictation).toHaveBeenCalledWith({ idioma: 'en' }));

    fireEvent.click(screen.getByRole('switch', { name: 'Som de aviso' }));
    await waitFor(() => expect(api.updateDictation).toHaveBeenCalledWith({ som: false }));

    const recorder = screen.getByTestId('dictation-recorder');
    await waitFor(() => expect((recorder as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(recorder);
    fireEvent.keyDown(recorder, { code: 'F9', key: 'F9', ctrlKey: true, shiftKey: true });
    await waitFor(() => expect(api.updateDictation).toHaveBeenCalledWith({ teclas: 'ctrl+shift+f9' }));
  });

  it('mostra quando a combinação está em uso e o erro do servidor', async () => {
    api.fetchDictation.mockResolvedValue({ ...base, ativo: true, estado: 'em_uso', mensagem: 'em uso' });
    api.updateDictation.mockRejectedValue(new Error('Ctrl + Alt + N já é o atalho que chama o Nicx; escolha outra.'));
    render(<DictationSettings onSaved={() => {}} />);

    await waitFor(() => expect(screen.getByTestId('dictation-state').textContent).toBe('Em uso por outro programa'));
    expect(screen.getByText(/Outro programa já usa essa combinação/)).toBeTruthy();

    const recorder = screen.getByTestId('dictation-recorder');
    fireEvent.click(recorder);
    fireEvent.keyDown(recorder, { code: 'KeyN', key: 'n', ctrlKey: true, altKey: true });
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText(/já é o atalho que chama o Nicx/)).toBeTruthy();
  });

  it('sabe quando o ditado está ouvindo', () => {
    expect(isDictating('ouvindo')).toBe(true);
    expect(isDictating('transcrevendo')).toBe(true);
    expect(isDictating('pronto')).toBe(false);
    expect(isDictating(null)).toBe(false);
  });
});
