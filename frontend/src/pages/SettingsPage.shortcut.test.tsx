// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/store', () => ({ useAppStore: vi.fn() }));

import { ShortcutRecorder } from './SettingsPage';
import { comboFromKeyEvent, formatCombo } from '../lib/shortcut';

const none = { ctrlKey: false, altKey: false, shiftKey: false, metaKey: false };

// Os testes rodam com os textos em português (src/i18n/test-setup.ts).
describe('combinação do atalho a partir das teclas', () => {
  it('monta a forma do servidor na ordem ctrl, alt, shift, win', () => {
    expect(comboFromKeyEvent({ ...none, code: 'KeyN', altKey: true, ctrlKey: true })).toEqual({
      kind: 'done',
      combo: 'ctrl+alt+n',
    });
    expect(comboFromKeyEvent({ ...none, code: 'Space', ctrlKey: true, shiftKey: true })).toEqual({
      kind: 'done',
      combo: 'ctrl+shift+space',
    });
    expect(comboFromKeyEvent({ ...none, code: 'F9', metaKey: true, altKey: true })).toEqual({
      kind: 'done',
      combo: 'alt+win+f9',
    });
  });

  it('espera a tecla principal e recusa o que não serve', () => {
    expect(comboFromKeyEvent({ ...none, code: 'ControlLeft', ctrlKey: true })).toEqual({
      kind: 'pending',
      modifiers: ['ctrl'],
    });
    expect(comboFromKeyEvent({ ...none, code: 'Escape' })).toEqual({ kind: 'cancel' });
    expect(comboFromKeyEvent({ ...none, code: 'KeyN' })).toMatchObject({ reason: 'needModifier' });
    expect(comboFromKeyEvent({ ...none, code: 'KeyN', shiftKey: true })).toMatchObject({ reason: 'needModifier' });
    expect(comboFromKeyEvent({ ...none, code: 'Numpad1', ctrlKey: true })).toMatchObject({ reason: 'unsupportedKey' });
    expect(comboFromKeyEvent({ ...none, code: 'Delete', ctrlKey: true, altKey: true })).toMatchObject({
      reason: 'reserved',
    });
    expect(comboFromKeyEvent({ ...none, code: 'KeyL', metaKey: true })).toMatchObject({ reason: 'reserved' });
    expect(comboFromKeyEvent({ ...none, code: 'KeyC', ctrlKey: true })).toMatchObject({ reason: 'reserved' });
  });

  it('mostra a combinação para o usuário', () => {
    expect(formatCombo('ctrl+alt+n')).toBe('Ctrl + Alt + N');
    expect(formatCombo('ctrl+shift+space', { space: 'Espaço' })).toBe('Ctrl + Shift + Espaço');
  });
});

describe('ShortcutRecorder', () => {
  afterEach(cleanup);

  it('grava a combinação apertada', () => {
    const onChange = vi.fn();
    render(<ShortcutRecorder value="ctrl+alt+n" onChange={onChange} />);
    const field = screen.getByTestId('shortcut-recorder');
    expect(field.textContent).toBe('Ctrl + Alt + N');

    fireEvent.click(field);
    expect(field.textContent).toBe('Aperte as teclas…');
    fireEvent.keyDown(field, { code: 'ControlLeft', key: 'Control', ctrlKey: true });
    fireEvent.keyDown(field, { code: 'ShiftLeft', key: 'Shift', ctrlKey: true, shiftKey: true });
    expect(field.textContent).toBe('Ctrl + Shift + …');
    fireEvent.keyDown(field, { code: 'Space', key: ' ', ctrlKey: true, shiftKey: true });

    expect(onChange).toHaveBeenCalledWith('ctrl+shift+space');
  });

  it('avisa e não grava combinação do sistema; Esc cancela', () => {
    const onChange = vi.fn();
    render(<ShortcutRecorder value="ctrl+alt+n" onChange={onChange} />);
    const field = screen.getByTestId('shortcut-recorder');

    fireEvent.click(field);
    fireEvent.keyDown(field, { code: 'KeyL', key: 'l', metaKey: true });
    expect(screen.getByRole('alert').textContent).toContain('do sistema');
    fireEvent.keyDown(field, { code: 'KeyN', key: 'n' });
    expect(screen.getByRole('alert').textContent).toContain('Ctrl, Alt ou Win');

    fireEvent.keyDown(field, { code: 'Escape', key: 'Escape' });
    expect(field.textContent).toBe('Ctrl + Alt + N');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('teclas fora da gravação não mudam nada', () => {
    const onChange = vi.fn();
    render(<ShortcutRecorder value="ctrl+alt+n" onChange={onChange} />);
    fireEvent.keyDown(screen.getByTestId('shortcut-recorder'), { code: 'KeyK', ctrlKey: true, altKey: true });
    expect(onChange).not.toHaveBeenCalled();
  });
});
