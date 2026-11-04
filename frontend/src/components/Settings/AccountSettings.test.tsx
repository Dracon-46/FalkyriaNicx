// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AccountState } from '../../lib/conta';

const api = vi.hoisted(() => ({
  contaEstado: vi.fn(),
  cadastrar: vi.fn(),
  confirmar: vi.fn(),
  reenviar: vi.fn(),
  entrar: vi.fn(),
  esqueci: vi.fn(),
  redefinir: vi.fn(),
  sair: vi.fn(),
  aceitar: vi.fn(),
  mudarNome: vi.fn(),
  listarBackups: vi.fn(),
  fazerBackup: vi.fn(),
  previaBackup: vi.fn(),
  restaurarBackup: vi.fn(),
  apagarBackup: vi.fn(),
  exportarDados: vi.fn(),
  apagarConta: vi.fn(),
  baixarDados: vi.fn(),
}));

vi.mock('../../lib/conta', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../lib/conta')>()),
  ...api,
}));

import { AccountSettings } from './AccountSettings';

const fora: AccountState = { conectado: false, protegido: true, termos_versao: '2026-11-04', politica_versao: '2026-11-04' };
const dentro: AccountState = { ...fora, conectado: true, email: 'pessoa@exemplo.com', nome: 'Pessoa', precisa_aceitar: false, criado_em: '2026-11-04T10:00:00Z' };

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockReset();
  api.listarBackups.mockResolvedValue([]);
});
afterEach(cleanup);

describe('AccountSettings', () => {
  it('criar conta exige o aceite e pede o código', async () => {
    api.contaEstado.mockResolvedValue(fora);
    api.cadastrar.mockResolvedValue({ confirmar: true });
    api.confirmar.mockResolvedValue(dentro);
    render(<AccountSettings />);
    fireEvent.click(await screen.findByTestId('account-tab-criar'));
    fireEvent.change(screen.getByTestId('account-email'), { target: { value: 'pessoa@exemplo.com' } });
    fireEvent.change(screen.getByTestId('account-password'), { target: { value: 'senhaforte123' } });
    fireEvent.click(screen.getByTestId('account-submit'));
    expect(await screen.findByText('Para criar a conta, aceite os Termos de Uso e a Política de Privacidade.')).toBeTruthy();
    expect(api.cadastrar).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('account-consent'));
    fireEvent.click(screen.getByTestId('account-submit'));
    await waitFor(() => expect(api.cadastrar).toHaveBeenCalledWith('pessoa@exemplo.com', 'senhaforte123', '', true));
    expect(await screen.findByText(/Enviamos um e-mail para pessoa@exemplo.com/)).toBeTruthy();
    fireEvent.change(screen.getByTestId('account-code'), { target: { value: '1234 5678' } });
    fireEvent.click(screen.getByTestId('account-submit'));
    await waitFor(() => expect(api.confirmar).toHaveBeenCalledWith('pessoa@exemplo.com', '12345678'));
    expect((await screen.findByTestId('account-email-shown')).textContent).toContain('pessoa@exemplo.com');
  });

  it('erro do servidor aparece em português', async () => {
    api.contaEstado.mockResolvedValue(fora);
    api.entrar.mockRejectedValue(new Error('Não deu: e-mail ou senha errados'));
    render(<AccountSettings />);
    fireEvent.change(await screen.findByTestId('account-email'), { target: { value: 'x@y.com' } });
    fireEvent.change(screen.getByTestId('account-password'), { target: { value: 'abc' } });
    fireEvent.click(screen.getByTestId('account-submit'));
    expect(await screen.findByText('Não deu: e-mail ou senha errados')).toBeTruthy();
  });

  it('faz backup só com senha de 8+ e restaura depois de abrir', async () => {
    api.contaEstado.mockResolvedValue(dentro);
    const resumo = { assistentes: 2, rotinas: 1, habilidades: 3, mcp: 0, pacotes_instalados: 0 };
    api.fazerBackup.mockResolvedValue({ id: 'b1', rotulo: 'Casa', versao_nicx: '0.2.0', tamanho: 2048, criado_em: '2026-11-04T10:00:00Z', resumo });
    render(<AccountSettings />);
    const criar = (await screen.findByTestId('backup-create')) as HTMLButtonElement;
    fireEvent.change(screen.getByTestId('backup-secret'), { target: { value: 'curta' } });
    expect(criar.disabled).toBe(true);
    fireEvent.change(screen.getByTestId('backup-secret'), { target: { value: 'senha-do-backup' } });
    api.listarBackups.mockResolvedValue([{ id: 'b1', rotulo: 'Casa', versao_nicx: '0.2.0', tamanho: 2048, criado_em: '2026-11-04T10:00:00Z' }]);
    fireEvent.click(criar);
    expect(await screen.findByText('Backup feito: 2 assistentes, 1 rotinas, 3 habilidades, 0 servidores.')).toBeTruthy();
    api.previaBackup.mockResolvedValue(resumo);
    api.restaurarBackup.mockResolvedValue({ pulados: [] });
    fireEvent.click(await screen.findByTestId('backup-restore-b1'));
    fireEvent.change(screen.getByTestId('backup-restore-secret'), { target: { value: 'senha-do-backup' } });
    fireEvent.click(screen.getByTestId('backup-open'));
    expect((await screen.findByTestId('backup-summary')).textContent).toContain('2 assistentes');
    fireEvent.click(screen.getByTestId('backup-apply'));
    await waitFor(() => expect(api.restaurarBackup).toHaveBeenCalledWith('b1', 'senha-do-backup'));
    expect(await screen.findByText('Backup restaurado.')).toBeTruthy();
  });

  it('conta antiga precisa aceitar antes de usar o backup', async () => {
    api.contaEstado.mockResolvedValue({ ...dentro, precisa_aceitar: true });
    api.aceitar.mockResolvedValue(dentro);
    render(<AccountSettings />);
    expect(await screen.findByTestId('account-needs-consent')).toBeTruthy();
    expect(screen.queryByTestId('account-backups')).toBeNull();
    fireEvent.click(screen.getByTestId('account-consent'));
    fireEvent.click(screen.getByTestId('account-accept'));
    expect(await screen.findByTestId('account-backups')).toBeTruthy();
  });

  it('exportar baixa os dados e apagar pede a senha', async () => {
    api.contaEstado.mockResolvedValueOnce(dentro).mockResolvedValue(fora);
    api.exportarDados.mockResolvedValue({ conta: { email: 'pessoa@exemplo.com' } });
    api.apagarConta.mockResolvedValue(undefined);
    render(<AccountSettings />);
    fireEvent.click(await screen.findByTestId('account-export'));
    await waitFor(() => expect(api.baixarDados).toHaveBeenCalledWith({ conta: { email: 'pessoa@exemplo.com' } }));
    fireEvent.click(screen.getByTestId('account-delete'));
    const confirmar = screen.getByTestId('account-delete-confirm') as HTMLButtonElement;
    expect(confirmar.disabled).toBe(true);
    fireEvent.change(screen.getByTestId('account-delete-password'), { target: { value: 'senhaforte123' } });
    fireEvent.click(confirmar);
    await waitFor(() => expect(api.apagarConta).toHaveBeenCalledWith('senhaforte123'));
    expect(await screen.findByTestId('account-tab-criar')).toBeTruthy();
  });
});
