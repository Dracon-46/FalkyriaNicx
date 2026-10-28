import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import {
  CustomEndpointSetup,
  InferenceRecoveryButton,
  InferenceSourceChooser,
  OllamaConsent,
  inferenceSetupReducer,
  persistAndStartInferenceSource,
  type InferenceSourceSubmission,
} from './InferenceSourceSetup';

describe('first-run inference source navigation', () => {
  it('requires a second, explicit confirmation before local setup', () => {
    expect(inferenceSetupReducer('choose', 'choose_ollama')).toBe('ollama');
    expect(inferenceSetupReducer('ollama', 'back')).toBe('choose');
  });

  it('lets custom endpoint setup cancel safely back to the chooser', () => {
    expect(inferenceSetupReducer('choose', 'choose_custom')).toBe('custom');
    expect(inferenceSetupReducer('custom', 'back')).toBe('choose');
  });

  it('renders both sources without claiming either has started', () => {
    const html = renderToStaticMarkup(<InferenceSourceChooser onChoose={vi.fn()} />);

    expect(html).toContain('Ollama local');
    expect(html).toContain('Servidor compatível com OpenAI');
    expect(html).toContain('Nada é instalado, iniciado ou baixado até você confirmar');
    expect(html).not.toContain('Iniciando a configuração local');
  });

  it('discloses the model download and offers a no-op back path', () => {
    const html = renderToStaticMarkup(
      <OllamaConsent onBack={vi.fn()} onConfirm={vi.fn()} />,
    );

    expect(html).toContain('pode baixar um modelo');
    expect(html).toContain('vários gigabytes');
    expect(html).toContain('Se você voltar, o Ollama continua parado');
    expect(html).toContain('Usar o Ollama e continuar');
    expect(html).toContain('Voltar');
  });

  it('requires endpoint coordinates and keeps an explicit cancel control', () => {
    const html = renderToStaticMarkup(
      <CustomEndpointSetup onCancel={vi.fn()} onConfirm={vi.fn()} />,
    );

    expect(html).toContain('URL do servidor');
    expect(html).toContain('ID do modelo');
    expect(html).toMatch(/aria-label="URL do servidor"[^>]*required/);
    expect(html).toMatch(/aria-label="ID do modelo"[^>]*required/);
    expect(html).toContain('O Ollama não vai iniciar nem baixar modelos');
    expect(html).toContain('Cancelar');
  });

  it('renders a source-change recovery action with a guarded busy state', () => {
    const ready = renderToStaticMarkup(
      <InferenceRecoveryButton recovering={false} onChange={vi.fn()} />,
    );
    const stopping = renderToStaticMarkup(
      <InferenceRecoveryButton recovering onChange={vi.fn()} />,
    );

    expect(ready).toContain('Trocar a fonte da IA');
    expect(ready).not.toMatch(/ disabled(?:=""|>)/);
    expect(stopping).toContain('Parando a configuração...');
    expect(stopping).toMatch(/ disabled(?:=""|>)/);
  });
});

describe('first-run inference source persistence', () => {
  it('persists the exact choice before requesting backend startup', async () => {
    const calls: string[] = [];
    const persist = vi.fn(async (source: InferenceSourceSubmission) => {
      calls.push(`persist:${source.kind}`);
    });
    const start = vi.fn(async () => {
      calls.push('start');
    });

    await persistAndStartInferenceSource(
      { kind: 'custom', host: 'http://localhost:1234', model: 'local-model', engine: 'lmstudio' },
      persist,
      start,
    );

    expect(calls).toEqual(['persist:custom', 'start']);
    expect(persist).toHaveBeenCalledWith({
      kind: 'custom',
      host: 'http://localhost:1234',
      model: 'local-model',
      engine: 'lmstudio',
    });
  });

  it('does not start anything when persistence fails', async () => {
    const persist = vi.fn(async () => {
      throw new Error('secure storage unavailable');
    });
    const start = vi.fn(async () => {});

    await expect(
      persistAndStartInferenceSource({ kind: 'ollama' }, persist, start),
    ).rejects.toThrow('secure storage unavailable');
    expect(start).not.toHaveBeenCalled();
  });

  it('rolls a staged choice back when startup rejects', async () => {
    const calls: string[] = [];
    const persist = vi.fn(async () => {
      calls.push('persist');
    });
    const start = vi.fn(async () => {
      calls.push('start');
      throw new Error('endpoint unavailable');
    });
    const rollback = vi.fn(async () => {
      calls.push('rollback');
    });

    await expect(
      persistAndStartInferenceSource(
        { kind: 'custom', host: 'http://localhost:1234', model: 'missing' },
        persist,
        start,
        rollback,
      ),
    ).rejects.toThrow('endpoint unavailable');
    expect(calls).toEqual(['persist', 'start', 'rollback']);
  });
});
