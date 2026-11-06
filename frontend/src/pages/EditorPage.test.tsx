// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { forwardRef, useImperativeHandle, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const nicx = vi.hoisted(() => ({ conversar: vi.fn() }));
vi.mock('../lib/editor/nicx', async (original) => ({ ...(await original<typeof import('../lib/editor/nicx')>()), conversar: nicx.conversar }));

// O CodeMirror precisa de layout de verdade: aqui, uma imitação com a mesma API.
const trocas: Array<[number, number, string]> = [];
vi.mock('../components/Editor/CodeEditor', () => ({
  CodeEditor: forwardRef(function Falso({ texto, onChange }: { texto: string; onChange: (t: string) => void }, ref) {
    const [valor, setValor] = useState(texto);
    useImperativeHandle(ref, () => ({
      selecao: () => ({ de: 0, ate: 0, texto: '', linhaInicial: 1, linhaFinal: 1 }),
      selecaoEmLinhas: () => ({ de: 0, ate: valor.length, texto: valor, linhaInicial: 1, linhaFinal: 1 }),
      texto: () => valor,
      trocar: (de: number, ate: number, novo: string) => {
        trocas.push([de, ate, novo]);
        setValor(valor.slice(0, de) + novo + valor.slice(ate));
        onChange(valor.slice(0, de) + novo + valor.slice(ate));
      },
      inserir: () => {},
      focar: () => {},
    }));
    return <textarea data-testid="falso-editor" value={valor} onChange={(e) => { setValor(e.target.value); onChange(e.target.value); }} />;
  }),
}));
vi.mock('../components/Editor/PropostaDiff', () => ({
  PropostaDiff: ({ proposta, onAplicar, onDescartar }: { proposta: string; onAplicar: () => void; onDescartar: () => void }) => (
    <div data-testid="editor-proposta">
      <pre>{proposta}</pre>
      <button onClick={onAplicar}>aplicar</button>
      <button onClick={onDescartar}>descartar</button>
    </div>
  ),
}));

import { useAppStore } from '../lib/store';
import { EditorPage } from './EditorPage';

async function abrirArquivo(conteudo: string, nome = 'calc.py') {
  render(<EditorPage />);
  const entrada = document.querySelector('input[type=file]') as HTMLInputElement;
  const arquivo = new File([conteudo], nome, { type: 'text/plain' });
  Object.defineProperty(entrada, 'files', { value: [arquivo] });
  fireEvent.change(entrada);
  await screen.findByTestId('falso-editor');
}

beforeEach(() => {
  trocas.length = 0;
  useAppStore.setState({ selectedModel: 'qwen3.5:4b' });
});
afterEach(() => cleanup());

describe('editor de código', () => {
  it('Corrigir abre o diff e Aplicar troca o trecho', async () => {
    nicx.conversar.mockImplementation(async function* () {
      yield '```python\nreturn total / len(valores)\n```\nCorrigi o nome.';
    });
    await abrirArquivo('return total / len(valore)\n');
    fireEvent.click(screen.getByTestId('editor-corrigir'));
    const diff = await screen.findByTestId('editor-proposta');
    expect(diff.textContent).toContain('len(valores)');
    fireEvent.click(screen.getByText('aplicar'));
    const original = 'return total / len(valore)\n';
    await waitFor(() => expect(trocas).toEqual([[0, original.length, 'return total / len(valores)\n']]));
    expect(screen.queryByTestId('editor-proposta')).toBeNull();
    // Mudou e não salvou: o botão "Baixar" fica ativo.
    expect((screen.getByTestId('editor-salvar') as HTMLButtonElement).disabled).toBe(false);
  });

  it('Explicar mostra a resposta sem mexer no código', async () => {
    nicx.conversar.mockImplementation(async function* () {
      yield 'Calcula a média.';
    });
    await abrirArquivo('x = 1\n');
    fireEvent.click(screen.getByTestId('editor-explicar'));
    expect(await screen.findByText('Calcula a média.')).toBeTruthy();
    expect(screen.queryByTestId('editor-proposta')).toBeNull();
    expect(trocas).toEqual([]);
  });

  it('arquivo binário não abre', async () => {
    render(<EditorPage />);
    const entrada = document.querySelector('input[type=file]') as HTMLInputElement;
    Object.defineProperty(entrada, 'files', { value: [new File(['a\u0000b'], 'img.png')] });
    fireEvent.change(entrada);
    await waitFor(() => expect(screen.queryByTestId('falso-editor')).toBeNull());
    expect(screen.getByText(/Abra uma pasta ou um arquivo/)).toBeTruthy();
  });
});
