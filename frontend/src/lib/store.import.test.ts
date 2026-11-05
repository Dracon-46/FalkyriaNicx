import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const CONVERSATIONS_KEY = 'nicx-conversations';

class MemoryStorage {
  private store = new Map<string, string>();

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }
}

function conversa(id: string, updatedAt: number, title = id) {
  return { id, title, createdAt: 1, updatedAt, model: 'qwen3.5:4b', messages: [] };
}

beforeEach(() => {
  vi.resetModules();
  (globalThis as unknown as { localStorage: MemoryStorage }).localStorage =
    new MemoryStorage();
});

afterEach(() => {
  (globalThis as unknown as { localStorage?: MemoryStorage }).localStorage =
    undefined;
});

describe('importConversations', () => {
  it('junta com as conversas que já existem em vez de substituir', async () => {
    localStorage.setItem(
      CONVERSATIONS_KEY,
      JSON.stringify({
        version: 1,
        activeId: 'a',
        conversations: { a: conversa('a', 50, 'minha'), b: conversa('b', 10) },
      }),
    );
    const { useAppStore } = await import('./store');

    const entraram = useAppStore.getState().importConversations({
      version: 1,
      activeId: 'x',
      conversations: {
        a: conversa('a', 20, 'antiga'), // mais velha que a daqui: fica a daqui
        b: conversa('b', 30, 'nova'), // mais nova: entra
        c: conversa('c', 5), // não existia: entra
      },
    });

    expect(entraram).toBe(2);
    const salvo = JSON.parse(localStorage.getItem(CONVERSATIONS_KEY)!);
    expect(Object.keys(salvo.conversations).sort()).toEqual(['a', 'b', 'c']);
    expect(salvo.conversations.a.title).toBe('minha');
    expect(salvo.conversations.b.title).toBe('nova');
    expect(salvo.activeId).toBe('a');
    expect(useAppStore.getState().conversations).toHaveLength(3);
  });

  it('recusa arquivo que não é exportação do Nicx sem mexer em nada', async () => {
    const antes = JSON.stringify({ version: 1, activeId: null, conversations: { a: conversa('a', 1) } });
    localStorage.setItem(CONVERSATIONS_KEY, antes);
    const { useAppStore } = await import('./store');

    expect(useAppStore.getState().importConversations(null)).toBe(-1);
    expect(useAppStore.getState().importConversations({ version: 2, conversations: {} })).toBe(-1);
    expect(useAppStore.getState().importConversations({ foo: 'bar' })).toBe(-1);
    expect(localStorage.getItem(CONVERSATIONS_KEY)).toBe(antes);
  });

  it('pula conversas quebradas e importa as boas', async () => {
    const { useAppStore } = await import('./store');
    const entraram = useAppStore.getState().importConversations({
      version: 1,
      conversations: {
        boa: conversa('boa', 3),
        semMensagens: { id: 'semMensagens', updatedAt: 1 },
        lixo: 'texto',
      },
    });
    expect(entraram).toBe(1);
    expect(useAppStore.getState().conversations.map((c) => c.id)).toEqual(['boa']);
  });
});
