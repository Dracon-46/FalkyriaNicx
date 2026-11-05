// @vitest-environment happy-dom
import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it } from 'vitest';
import { useAdmin } from '../../lib/conta';
import { useAppStore } from '../../lib/store';
import { Sidebar } from './Sidebar';

function abrir() {
  useAppStore.setState({ sidebarOpen: true });
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  useAdmin.setState({ admin: null });
});

describe('menu: Painel Falkyria só para administradores', () => {
  it('escondido enquanto confere e para quem não é administrador', () => {
    useAdmin.setState({ admin: null });
    abrir();
    expect(screen.queryByText('Painel Falkyria')).toBeNull();
    act(() => useAdmin.setState({ admin: false }));
    expect(screen.queryByText('Painel Falkyria')).toBeNull();
    expect(screen.getByText('Atualizações')).toBeTruthy();
  });

  it('aparece quando o banco confirma a conta de administrador', () => {
    useAdmin.setState({ admin: true });
    abrir();
    expect(screen.getByText('Painel Falkyria')).toBeTruthy();
  });
});
