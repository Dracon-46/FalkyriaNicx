import { useAppStore, generateId } from './store';
import { streamChat } from './sse';
import { fetchModels } from './api';
import type { SendOutcome } from './voice-conversation';
import type { ChatMessage, TokenUsage } from '../types';

let modelsRequest: Promise<void> | null = null;

/** Load the model list once (the store then picks the preferred model). */
export function ensureModels(): Promise<void> {
  const app = useAppStore.getState();
  if (app.selectedModel) return Promise.resolve();
  if (!modelsRequest) {
    modelsRequest = fetchModels()
      .then((models) => useAppStore.getState().setModels(models))
      .catch(() => useAppStore.getState().setModels([]))
      .finally(() => {
        useAppStore.getState().setModelsLoading(false);
        modelsRequest = null;
      });
  }
  return modelsRequest;
}

export interface SpokenChatOptions {
  /** Conversation to continue; a new one is created when it is missing. */
  conversationId?: string | null;
  onConversation?: (id: string) => void;
  signal?: AbortSignal;
}

/**
 * Send one spoken message and stream the reply into the store: the lean
 * version of the composer's send for the floating mascot (no attachments,
 * tools UI or Deep Research). The reply lands in the store like any other, so
 * the voice conversation reads it aloud and the mascot reacts to it.
 */
export async function sendSpokenMessage(
  text: string,
  options: SpokenChatOptions = {},
): Promise<SendOutcome> {
  const content = text.trim();
  if (!content) return 'not-sent';
  await ensureModels();
  const app = useAppStore.getState();
  if (app.streamState.isStreaming) return 'not-sent';
  const model = app.selectedModel;
  if (!model) {
    app.addLogEntry({
      timestamp: Date.now(),
      level: 'error',
      category: 'chat',
      message: 'Nenhum modelo disponível',
    });
    return 'not-sent';
  }

  let convId = options.conversationId ?? null;
  if (!convId || !app.conversations.some((c) => c.id === convId)) {
    convId = app.createConversation(model);
    options.onConversation?.(convId);
  } else if (app.activeId !== convId) {
    app.selectConversation(convId);
  }

  const userMsg: ChatMessage = { id: generateId(), role: 'user', content, timestamp: Date.now() };
  app.addMessage(convId, userMsg);
  const history = useAppStore.getState().messages.map((m) => ({ role: m.role, content: m.content }));
  app.addMessage(convId, { id: generateId(), role: 'assistant', content: '', timestamp: Date.now() });

  const started = Date.now();
  let reply = '';
  let usage: TokenUsage | undefined;
  let stopped = false;
  let lastFlush = 0;
  app.setStreamState({
    conversationId: convId,
    isStreaming: true,
    phase: 'Generating...',
    elapsedMs: 0,
    activeToolCalls: [],
    content: '',
  });

  try {
    for await (const event of streamChat(
      {
        model,
        messages: history,
        stream: true,
        temperature: app.settings.temperature,
        max_tokens: app.settings.maxTokens,
      },
      options.signal,
    )) {
      let data: any;
      try {
        data = JSON.parse(event.data);
      } catch {
        continue;
      }
      if (data?.usage) usage = data.usage;
      const delta = data?.choices?.[0]?.delta?.content;
      if (delta) {
        reply += delta;
        useAppStore.getState().setStreamState({ content: reply, phase: '' });
        const now = Date.now();
        if (now - lastFlush >= 120) {
          useAppStore.getState().updateLastAssistant(convId, reply);
          lastFlush = now;
        }
      }
      if (data?.choices?.[0]?.finish_reason === 'stop') break;
    }
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      stopped = true;
    } else {
      const message = err?.message || String(err);
      reply = reply || `Erro: ${message}`;
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(),
        level: 'error',
        category: 'chat',
        message: `Stream error: ${message}`,
      });
    }
  } finally {
    const store = useAppStore.getState();
    store.updateLastAssistant(
      convId,
      reply || (stopped ? '(Resposta interrompida)' : 'Não consegui responder. Tente de novo.'),
      undefined,
      usage,
      // Telemetry marks the reply as finished (the mascot cheers for it).
      stopped ? undefined : { model_id: model, total_ms: Date.now() - started },
    );
    store.resetStream();
  }
  return stopped ? 'stopped' : 'done';
}
