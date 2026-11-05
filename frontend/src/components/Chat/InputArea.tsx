import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, Square, Paperclip, Search, AudioLines, X, Loader2, Film } from 'lucide-react';
import { toast } from 'sonner';
import { useLocation, useNavigate } from 'react-router';
import { useAppStore, generateId } from '../../lib/store';
import { useTtsStore } from '../../lib/tts';
import { streamChat, streamResearch } from '../../lib/sse';
import { apiFetch, fetchSavings, getBase } from '../../lib/api';
import { listConnectors, getSyncStatus } from '../../lib/connectors-api';
import { serializeToolCallArguments } from '../../lib/tool-call';
import { appShortcut } from '../../lib/shortcut';
import {
  MAX_IMAGENS,
  contarImagens,
  guardarMiniaturas,
  prepararImagem,
  prepararVideo,
  textoParaModelo,
  tipoDoArquivo,
  videoPendente,
  type Anexo,
} from '../../lib/anexos';
import {
  engineFromCompletionChunk,
  resolveChatEngine,
} from '../../lib/chat-telemetry';
import { MicButton } from './MicButton';
import { useSpeech } from '../../hooks/useSpeech';
import { useVoiceConversation, type SendOutcome } from '../../hooks/useVoiceConversation';
import { NicxMascot } from '../Mascot/NicxMascot';
import { useTranslation } from 'react-i18next';
import i18n from '../../i18n';
import type {
  ChatMessage,
  MessageTelemetry,
  ResearchSearchTrace,
  ResearchSource,
  TokenUsage,
  ToolCallInfo,
} from '../../types';

/** Size of the mascot perched on the composer, in px. */
const PERCH_SIZE = 60;

// While Deep Research is toggled on, poll connected sources for sync
// progress so we can surface "Searching over N items — sync in progress"
// next to the toggle. Polling is gated on `enabled` so toggling DR off
// stops the network chatter immediately.
function useResearchCorpusSync(enabled: boolean): {
  syncing: boolean;
  itemsSynced: number;
} {
  const [state, setState] = useState({ syncing: false, itemsSynced: 0 });

  useEffect(() => {
    if (!enabled) {
      setState({ syncing: false, itemsSynced: 0 });
      return;
    }
    let cancelled = false;

    const poll = async () => {
      try {
        const list = await listConnectors();
        const connected = list.filter((c) => c.connected);
        if (connected.length === 0) {
          if (!cancelled) setState({ syncing: false, itemsSynced: 0 });
          return;
        }
        const results = await Promise.all(
          connected.map(async (c) => {
            try {
              return await getSyncStatus(c.connector_id);
            } catch {
              return null;
            }
          }),
        );
        let syncing = false;
        let itemsSynced = 0;
        for (const r of results) {
          if (!r) continue;
          if (r.state === 'syncing') syncing = true;
          itemsSynced += r.items_synced ?? 0;
        }
        if (!cancelled) setState({ syncing, itemsSynced });
      } catch {
        // Network blip — leave previous state intact.
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [enabled]);

  return state;
}

// A resposta em andamento é uma só para o app inteiro: ficam fora do
// componente para o "Parar" funcionar depois de ir às Configurações e voltar
// (o InputArea é montado de novo e um useRef nasceria vazio).
const abortRef: { current: AbortController | null } = { current: null };
const timerRef: { current: ReturnType<typeof setInterval> | null } = { current: null };

export function InputArea() {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Imagens e vídeos que vão com a próxima mensagem.
  const [anexos, setAnexos] = useState<Anexo[]>([]);
  const anexosRef = useRef<Anexo[]>([]);
  anexosRef.current = anexos;
  const arquivoRef = useRef<HTMLInputElement>(null);
  const [arrastando, setArrastando] = useState(false);
  const videoAbort = useRef(new Map<string, AbortController>());

  const activeId = useAppStore((s) => s.activeId);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const streamState = useAppStore((s) => s.streamState);
  const messages = useAppStore((s) => s.messages);
  const speechEnabled = useAppStore((s) => s.settings.speechEnabled);
  const maxTokens = useAppStore((s) => s.settings.maxTokens);
  const temperature = useAppStore((s) => s.settings.temperature);
  const createConversation = useAppStore((s) => s.createConversation);
  const addMessage = useAppStore((s) => s.addMessage);
  const updateLastAssistant = useAppStore((s) => s.updateLastAssistant);
  const setStreamState = useAppStore((s) => s.setStreamState);
  const resetStream = useAppStore((s) => s.resetStream);
  const modelLoading = useAppStore((s) => s.modelLoading);
  const deepResearch = useAppStore((s) => s.deepResearch);
  const setDeepResearch = useAppStore((s) => s.setDeepResearch);
  const corpusSync = useResearchCorpusSync(deepResearch);
  const isCurrentChatStreaming = streamState.isStreaming && streamState.conversationId === activeId;

  const speech = useSpeech();
  const {
    state: speechState,
    error: speechError,
    available: speechAvailable,
    startRecording,
    stopRecording,
  } = speech;
  // Hands-free mode sends through sendMessage, which is defined further down.
  const sendSpokenRef = useRef<(text: string) => Promise<SendOutcome>>(async () => 'not-sent');
  // Stopping the conversation mid-reply also stops the reply being generated.
  const conversation = useVoiceConversation(
    speech,
    (text) => sendSpokenRef.current(text),
    () => abortRef.current?.abort(),
  );

  // "Nicx, ligar" without a window of its own opens the interface with
  // ?voz=1: start the hands-free conversation as soon as the voice is ready.
  const voiceParamHandled = useRef(false);
  const startConversation = conversation.start;
  useEffect(() => {
    if (voiceParamHandled.current || !speechEnabled || !speechAvailable) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('voz') !== '1') return;
    voiceParamHandled.current = true;
    params.delete('voz');
    const query = params.toString();
    window.history.replaceState(
      window.history.state,
      '',
      `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`,
    );
    startConversation();
  }, [speechEnabled, speechAvailable, startConversation]);

  // Abort in-flight stream when the user switches models mid-generation.
  // This prevents errors from trying to continue a stream with a stale model.
  const prevModelRef = useRef(selectedModel);
  useEffect(() => {
    if (prevModelRef.current !== selectedModel && streamState.isStreaming) {
      abortRef.current?.abort();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      resetStream();
      abortRef.current = null;
    }
    prevModelRef.current = selectedModel;
  }, [selectedModel, streamState.isStreaming, resetStream]);

  const micDisabled =
    !speechEnabled || !speechAvailable || streamState.isStreaming || conversation.active;
  const micReason: 'not-enabled' | 'no-backend' | 'streaming' | undefined =
    !speechEnabled ? 'not-enabled'
    : !speechAvailable ? 'no-backend'
    : streamState.isStreaming ? 'streaming'
    : undefined;

  useEffect(() => {
    if (speechError) {
      toast.error(speechError, { duration: 8000 });
    }
  }, [speechError]);

  const handleMicClick = useCallback(async () => {
    if (speechState === 'recording') {
      try {
        const text = await stopRecording();
        if (text) {
          setInput((prev) => (prev ? prev + ' ' + text : text));
        }
      } catch {
        // Error is captured in useSpeech
      }
    } else {
      await startRecording();
    }
  }, [speechState, startRecording, stopRecording]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [input]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    resetStream();
  }, [resetStream]);

  // `spoken` is a hands-free utterance: sent as is, leaving the typed draft alone.
  const sendMessage = useCallback(async (spoken?: string): Promise<SendOutcome> => {
    const content = (spoken ?? input).trim();
    // A fala do modo mãos-livres não leva os anexos do campo.
    const usados = spoken === undefined ? anexosRef.current : [];
    if ((!content && usados.length === 0) || streamState.isStreaming) return 'not-sent';
    if (usados.some((a) => a.preparando)) {
      toast(i18n.t('chat.attach.waitVideo'));
      return 'not-sent';
    }
    // Pesquisa profunda é só texto: com anexo, vai pela conversa normal.
    const pesquisar = deepResearch && usados.length === 0;
    if (!selectedModel) {
      toast.error(i18n.t('chat.input.pickModel', { shortcut: appShortcut('k') }));
      return 'not-sent';
    }

    if (spoken === undefined) {
      setInput('');
      if (usados.length) setAnexos([]);
    }
    // A new question silences whatever Nicx is still saying.
    useTtsStore.getState().stop();
    let stopped = false;

    let convId = activeId;
    if (!convId) {
      convId = createConversation(selectedModel);
    }

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
      ...(usados.length ? { attachments: usados.map((a) => ({ tipo: a.tipo, nome: a.nome })) } : {}),
    };
    guardarMiniaturas(userMsg.id, usados);
    addMessage(convId, userMsg);

    // Build API messages before adding assistant placeholder
    const currentMessages = useAppStore.getState().messages;
    const apiMessages: Array<{ role: string; content: string; images?: string[] }> = currentMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    if (usados.length && apiMessages.length) {
      // Só a mensagem nova leva as imagens (e a fala dos vídeos).
      const ultima = apiMessages[apiMessages.length - 1];
      ultima.content = textoParaModelo(content, usados);
      ultima.images = usados.flatMap((a) => a.imagens);
    }

    const assistantMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isResearch: pesquisar || undefined,
    };
    addMessage(convId, assistantMsg);

    // Start streaming
    const startTime = Date.now();
    const timer = setInterval(() => {
      setStreamState({ elapsedMs: Date.now() - startTime });
    }, 100);
    timerRef.current = timer;

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedContent = '';
    let usage: TokenUsage | undefined;
    let complexity: { score: number; tier: string; suggested_max_tokens: number } | undefined;
    let routedEngine: string | undefined;
    const toolCalls: ToolCallInfo[] = [];
    const researchTraces: ResearchSearchTrace[] = [];
    const researchSourcesByRef = new Map<number, ResearchSource>();
    const flushSources = () =>
      Array.from(researchSourcesByRef.values()).sort((a, b) => a.ref - b.ref);
    let lastFlush = 0;
    let ttftMs: number | undefined;

    setStreamState({
      conversationId: convId,
      isStreaming: true,
      phase: pesquisar ? i18n.t('chat.phase.researching') : i18n.t('chat.phase.generating'),
      elapsedMs: 0,
      activeToolCalls: [],
      content: '',
    });
    useAppStore.getState().addLogEntry({
      timestamp: Date.now(),
      level: 'info',
      category: 'chat',
      message: pesquisar
        ? i18n.t('chat.log.research', { text: `${content.slice(0, 80)}${content.length > 80 ? '...' : ''}` })
        : i18n.t('chat.log.request', { text: `${content.slice(0, 80)}${content.length > 80 ? '...' : ''}`, model: selectedModel }),
    });

    try {
      if (pesquisar) {
        for await (const ev of streamResearch(
          content,
          selectedModel,
          controller.signal,
        )) {
          if (ev.type === 'search_call') {
            const trace: ResearchSearchTrace = {
              id: generateId(),
              query: ev.arguments?.query ?? '',
              person: ev.arguments?.person,
              timeRange: ev.arguments?.time_range,
              status: 'pending',
            };
            researchTraces.push(trace);
            setStreamState({ phase: i18n.t('chat.phase.searching', { query: trace.query }) });
            updateLastAssistant(
              convId,
              accumulatedContent,
              undefined,
              undefined,
              undefined,
              undefined,
              [...researchTraces],
              flushSources(),
            );
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(),
              level: 'info',
              category: 'tool',
              message: trace.person
                ? i18n.t('chat.log.searchPerson', { query: trace.query, person: trace.person })
                : i18n.t('chat.log.search', { query: trace.query }),
            });
          } else if (ev.type === 'search_result') {
            const pending = [...researchTraces].reverse().find((t) => t.status === 'pending');
            if (pending) {
              pending.status = 'complete';
              pending.numHits = ev.num_hits;
              pending.topTitles = ev.top_titles;
            }
            if (ev.sources) {
              for (const src of ev.sources) {
                if (src && typeof src.ref === 'number' && !researchSourcesByRef.has(src.ref)) {
                  researchSourcesByRef.set(src.ref, src);
                }
              }
            }
            updateLastAssistant(
              convId,
              accumulatedContent,
              undefined,
              undefined,
              undefined,
              undefined,
              [...researchTraces],
              flushSources(),
            );
          } else if (ev.type === 'synthesis') {
            if (!ttftMs) ttftMs = Date.now() - startTime;
            accumulatedContent += ev.text;
            setStreamState({ content: accumulatedContent, phase: '' });
            const now = Date.now();
            if (now - lastFlush >= 80) {
              updateLastAssistant(
                convId,
                accumulatedContent,
                undefined,
                undefined,
                undefined,
                undefined,
                [...researchTraces],
                flushSources(),
              );
              lastFlush = now;
            }
          } else if (ev.type === 'system_metrics') {
            // Live GPU sample — feed straight to the System panel so Power
            // (W) and Energy (kJ) tick up in real time as the agent runs.
            useAppStore.getState().setLiveEnergy({
              power_w: ev.power_w,
              energy_j: ev.energy_j,
              duration_s: ev.duration_s,
            });
          } else if (ev.type === 'error') {
            // Backend setup/worker failure (Ollama down, planner model
            // missing, KnowledgeStore locked, etc.). Without surfacing the
            // message, the user sees only the generic "No response was
            // generated" fallback and has no way to self-diagnose.
            const msg = ev.message || i18n.t('chat.research.failedNoDetail');
            accumulatedContent = accumulatedContent
              ? `${accumulatedContent}\n\n**${i18n.t('chat.research.stopped')}** ${msg}`
              : `**${i18n.t('chat.research.failed')}** ${msg}`;
            setStreamState({ content: accumulatedContent, phase: '' });
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(),
              level: 'error',
              category: 'chat',
              message: i18n.t('chat.log.researchError', { message: msg }),
            });
            toast.error(msg, { duration: 8000 });
          } else if (ev.type === 'done') {
            if (ev.usage) {
              usage = {
                prompt_tokens: ev.usage.prompt_tokens ?? 0,
                completion_tokens: ev.usage.completion_tokens ?? 0,
                total_tokens:
                  ev.usage.total_tokens ??
                  (ev.usage.prompt_tokens ?? 0) +
                    (ev.usage.completion_tokens ?? 0),
              };
              // Optimistically roll this research turn into the session
              // counters so the Session panel updates the moment the
              // stream finishes, regardless of how /v1/savings aggregates
              // research telemetry server-side.
              useAppStore.getState().incrementSavings(usage);
            }
            // Hold the final live numbers visible for a beat so the panel
            // doesn't flash to 0 between the SSE close and the next
            // /v1/telemetry/energy poll picking up the persisted record.
            window.setTimeout(() => {
              useAppStore.getState().setLiveEnergy(null);
            }, 1500);
            break;
          }
        }
      } else {
      for await (const sseEvent of streamChat(
        {
          model: selectedModel,
          messages: apiMessages,
          stream: true,
          temperature,
          max_tokens: maxTokens,
          voice: spoken !== undefined,
        },
        controller.signal,
      )) {
        const eventName = sseEvent.event;

        if (eventName === 'agent_turn_start') {
          setStreamState({ phase: i18n.t('chat.phase.thinking') });
        } else if (eventName === 'inference_start') {
          setStreamState({ phase: i18n.t('chat.phase.generating') });
          useAppStore.getState().addLogEntry({
            timestamp: Date.now(), level: 'info', category: 'chat',
            message: i18n.t('chat.log.generatingWith', { model: selectedModel }),
          });
        } else if (eventName === 'tool_call_start') {
          try {
            const data = JSON.parse(sseEvent.data);
            const tc: ToolCallInfo = {
              id: generateId(),
              tool: data.tool,
              arguments: serializeToolCallArguments(data.arguments),
              status: 'running',
            };
            toolCalls.push(tc);
            setStreamState({
              phase: i18n.t('chat.phase.callingTool', { tool: data.tool }),
              activeToolCalls: [...toolCalls],
            });
            updateLastAssistant(convId, accumulatedContent, [...toolCalls]);
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(), level: 'info', category: 'tool',
              message: i18n.t('chat.log.callingTool', { call: `${data.tool}(${serializeToolCallArguments(data.arguments)})` }),
            });
          } catch {}
        } else if (eventName === 'tool_call_end') {
          try {
            const data = JSON.parse(sseEvent.data);
            const tc = toolCalls.find(
              (t) => t.tool === data.tool && t.status === 'running',
            );
            if (tc) {
              tc.status = data.success ? 'success' : 'error';
              tc.latency = data.latency;
              tc.result = data.result;
            }
            setStreamState({
              phase: i18n.t('chat.phase.generating'),
              activeToolCalls: [...toolCalls],
            });
            updateLastAssistant(convId, accumulatedContent, [...toolCalls]);
          } catch {}
        } else {
          try {
            const data = JSON.parse(sseEvent.data);
            const delta = data.choices?.[0]?.delta;
            if (data.usage) usage = data.usage;
            if (data.complexity) complexity = data.complexity;
            routedEngine = engineFromCompletionChunk(data) ?? routedEngine;
            if (delta?.content) {
              if (!ttftMs) ttftMs = Date.now() - startTime;
              accumulatedContent += delta.content;
              setStreamState({ content: accumulatedContent, phase: '' });

              const now = Date.now();
              if (now - lastFlush >= 80) {
                updateLastAssistant(
                  convId,
                  accumulatedContent,
                  toolCalls.length > 0 ? [...toolCalls] : undefined,
                );
                lastFlush = now;
              }
            }
            if (data.choices?.[0]?.finish_reason === 'stop') break;
          } catch {}
        }
      }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        stopped = true;
        // User cancelled or model switch — keep whatever was accumulated
        if (!accumulatedContent) accumulatedContent = i18n.t('chat.reply.stopped');
      } else {
        const errMsg = err?.message || String(err);
        accumulatedContent =
          accumulatedContent || i18n.t('chat.reply.error', { message: errMsg });
        useAppStore.getState().addLogEntry({
          timestamp: Date.now(), level: 'error', category: 'chat',
          message: i18n.t('chat.log.streamError', { message: errMsg }),
        });
      }
      // If we tore out mid-research, make sure the live System panel
      // numbers don't get stuck on the last sample.
      useAppStore.getState().setLiveEnergy(null);
    } finally {
      if (!accumulatedContent) {
        accumulatedContent = i18n.t('chat.reply.empty');
      }
      const totalMs = Date.now() - startTime;
      const appState = useAppStore.getState();
      const selectedOwner = appState.models.find((m) => m.id === selectedModel)?.owned_by;
      const engineLabel = resolveChatEngine({
        routedEngine,
        serverEngine: appState.serverInfo?.engine,
        selectedModel,
        selectedOwner,
      });
      const telemetry: MessageTelemetry = {
        engine: engineLabel,
        model_id: selectedModel,
        total_ms: totalMs,
        ttft_ms: ttftMs,
        tokens_per_sec: usage?.completion_tokens
          ? usage.completion_tokens / (totalMs / 1000)
          : undefined,
        complexity_score: complexity?.score,
        complexity_tier: complexity?.tier,
        suggested_max_tokens: complexity?.suggested_max_tokens,
      };
      // Áudio só quando ESTA resposta gerou o resumo do dia: antes o player
      // do resumo aparecia em toda resposta depois que existia um.
      let audioMeta: { url: string } | undefined;
      if (abortRef.current === controller) {
        try {
          const digestRes = await apiFetch('/api/digest');
          if (digestRes.ok) {
            const digest = await digestRes.json();
            const geradoEm = Date.parse(digest.generated_at ?? '');
            if (digest.audio_available && geradoEm >= startTime) {
              audioMeta = { url: `${getBase()}/api/digest/audio` };
            }
          }
        } catch {
          // Sem resumo ou servidor indisponível: sem áudio.
        }
      }
      // Parou e mandou outra antes deste "finally": não mexe no envio novo.
      if (abortRef.current !== controller && abortRef.current !== null) {
        return stopped ? 'stopped' : 'done';
      }

      // Primeiro destrava o campo: se gravar falhar (armazenamento cheio), o
      // chat não fica "gerando" para sempre.
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      resetStream();
      updateLastAssistant(
        convId,
        accumulatedContent,
        toolCalls.length > 0 ? toolCalls : undefined,
        usage,
        telemetry,
        audioMeta,
        researchTraces.length > 0 ? researchTraces : undefined,
        researchSourcesByRef.size > 0 ? flushSources() : undefined,
      );
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(), level: 'info', category: 'chat',
        message: i18n.t('chat.log.response', { chars: accumulatedContent.length }),
      });
      abortRef.current = null;

      // Research path updates session counters optimistically from the
      // `done` event's usage payload — re-fetching here would overwrite
      // it with a potentially stale snapshot if the server's research
      // telemetry hasn't been merged into /v1/savings yet.
      if (!pesquisar) {
        fetchSavings()
          .then((data) => useAppStore.getState().setSavings(data))
          .catch(() => {});
      }
    }
    return stopped ? 'stopped' : 'done';
  }, [
    input,
    activeId,
    selectedModel,
    streamState.isStreaming,
    createConversation,
    addMessage,
    updateLastAssistant,
    setStreamState,
    resetStream,
    deepResearch,
    temperature,
    maxTokens,
  ]);

  sendSpokenRef.current = sendMessage;

  // "Continuar de onde parei" (página Projetos): o pedido chega pela
  // navegação e sai como se tivesse sido digitado, assim que houver modelo.
  const location = useLocation();
  const navigate = useNavigate();
  const pendingPromptRef = useRef<string | null>(null);
  useEffect(() => {
    const prompt = (location.state as { nicxPrompt?: unknown } | null)?.nicxPrompt;
    if (typeof prompt !== 'string' || !prompt.trim()) return;
    pendingPromptRef.current = prompt;
    setInput(prompt);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.state, location.pathname, navigate]);
  useEffect(() => {
    const pending = pendingPromptRef.current;
    if (!pending || input !== pending || !selectedModel || streamState.isStreaming) return;
    pendingPromptRef.current = null;
    void sendMessage();
  }, [input, selectedModel, streamState.isStreaming, sendMessage]);

  const removerAnexo = (id: string) => {
    videoAbort.current.get(id)?.abort();
    videoAbort.current.delete(id);
    setAnexos((lista) => lista.filter((a) => a.id !== id));
  };

  const adicionarArquivos = async (arquivos: File[]) => {
    for (const arquivo of arquivos) {
      const tipo = tipoDoArquivo(arquivo);
      if (!tipo) {
        toast.error(t('chat.attach.notSupported', { name: arquivo.name }));
        continue;
      }
      const ocupadas = contarImagens(anexosRef.current);
      const pede = tipo === 'video' ? MAX_IMAGENS : 1;
      if (ocupadas + pede > MAX_IMAGENS) {
        toast.error(t('chat.attach.tooMany', { max: MAX_IMAGENS }));
        return;
      }
      if (tipo === 'imagem') {
        try {
          const anexo = await prepararImagem(arquivo, arquivo.name || t('chat.attach.pasted'));
          anexosRef.current = [...anexosRef.current, anexo];
          setAnexos(anexosRef.current);
        } catch (err) {
          toast.error(err instanceof Error ? err.message : String(err));
        }
        continue;
      }
      const pendente = videoPendente(arquivo);
      anexosRef.current = [...anexosRef.current, pendente];
      setAnexos(anexosRef.current);
      const parar = new AbortController();
      videoAbort.current.set(pendente.id, parar);
      prepararVideo(arquivo, pendente, parar.signal)
        .then((pronto) => {
          setAnexos((lista) => lista.map((a) => (a.id === pronto.id ? pronto : a)));
        })
        .catch((err) => {
          if (parar.signal.aborted) return;
          setAnexos((lista) => lista.filter((a) => a.id !== pendente.id));
          toast.error(err instanceof Error ? err.message : String(err));
        })
        .finally(() => videoAbort.current.delete(pendente.id));
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2" style={{ maxWidth: 'var(--chat-max-width)', margin: '0 auto', width: '100%' }}>
      <div className="mb-2 flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setDeepResearch(!deepResearch)}
            disabled={streamState.isStreaming}
            aria-pressed={deepResearch}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-50"
            style={{
              background: deepResearch ? 'var(--color-accent-subtle)' : 'transparent',
              border: `1px solid ${deepResearch ? 'var(--color-accent)' : 'var(--color-border)'}`,
              color: deepResearch ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
            }}
            title={deepResearch ? t('chat.input.deepResearchOn') : t('chat.input.deepResearchOff')}
          >
            <Search size={12} />
            {t('chat.input.deepResearch')}
          </button>
          {/* Hands-free: listen, send on silence, speak the reply, listen again. */}
          <button
            type="button"
            onClick={conversation.toggle}
            disabled={!conversation.active && (!speechEnabled || !speechAvailable)}
            aria-pressed={conversation.active}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-50"
            style={{
              background: conversation.active ? 'var(--color-accent-subtle)' : 'transparent',
              border: `1px solid ${conversation.active ? 'var(--color-accent)' : 'var(--color-border)'}`,
              color: conversation.active ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
            }}
            title={
              conversation.active
                ? t('chat.voice.stopHint')
                : !speechEnabled
                  ? t('chat.voice.enableHint')
                  : !speechAvailable
                    ? t('chat.voice.unavailable')
                    : t('chat.voice.startHint')
            }
          >
            <AudioLines
              size={12}
              style={{ animation: conversation.phase === 'listening' ? 'pulse 1.5s ease-in-out infinite' : 'none' }}
            />
            {conversation.label}
          </button>
          {/* Nicx sits on the composer and shows what it is doing. The empty
              chat already shows a big Nicx, so it only appears afterwards. */}
          {(messages.length > 0 || isCurrentChatStreaming) && (
            <NicxMascot
              size={PERCH_SIZE}
              interactive
              className="ml-auto relative z-[1]"
              style={{
                // Feet on the composer's top border (the body's base is at
                // 87.6% of the box); the empty top of the box overlaps upward.
                marginTop: -PERCH_SIZE * 0.2,
                marginBottom: -(8 + PERCH_SIZE * 0.124),
              }}
            />
          )}
        </div>
        {deepResearch && corpusSync.syncing && corpusSync.itemsSynced > 0 && (
          <div
            className="text-[11px] leading-snug"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            {t('chat.research.syncBefore')}{' '}
            <span key={corpusSync.itemsSynced} className="sync-bump" style={{ color: 'var(--color-text-secondary)' }}>
              {corpusSync.itemsSynced.toLocaleString(i18n.language)}
            </span>{' '}
            {t('chat.research.syncAfter')}
          </div>
        )}
      </div>
      {anexos.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2" data-testid="chat-attachments">
          {anexos.map((a) => (
            <div
              key={a.id}
              className="relative flex items-center gap-2 pl-1 pr-7 py-1 rounded-xl text-xs max-w-[14rem]"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
            >
              {a.miniatura ? (
                <img src={a.miniatura} alt="" className="w-10 h-10 rounded-lg object-cover shrink-0" />
              ) : (
                <span className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: 'var(--color-bg-tertiary)' }}>
                  {a.preparando ? <Loader2 size={14} className="animate-spin" /> : <Film size={14} />}
                </span>
              )}
              <span className="min-w-0">
                <span className="block truncate" style={{ color: 'var(--color-text)' }}>{a.nome}</span>
                {a.preparando && <span className="block">{t('chat.attach.preparingVideo')}</span>}
                {a.tipo === 'video' && !a.preparando && (
                  <span className="block">{t('chat.attach.videoReady', { frames: a.imagens.length })}</span>
                )}
              </span>
              <button
                type="button"
                onClick={() => removerAnexo(a.id)}
                className="absolute top-1 right-1 p-0.5 rounded cursor-pointer"
                style={{ color: 'var(--color-text-tertiary)' }}
                aria-label={t('chat.attach.remove', { name: a.nome })}
                title={t('chat.attach.remove', { name: a.nome })}
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      <div
        className="flex items-center gap-2 rounded-2xl px-4 py-3 transition-shadow"
        style={{
          background: 'var(--color-input-bg)',
          border: `1px ${arrastando ? 'dashed var(--color-accent)' : 'solid var(--color-input-border)'}`,
          boxShadow: 'var(--shadow-sm)',
        }}
        onDragOver={(e) => {
          if (!Array.from(e.dataTransfer.types).includes('Files')) return;
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          if (!e.dataTransfer.files.length) return;
          e.preventDefault();
          setArrastando(false);
          void adicionarArquivos(Array.from(e.dataTransfer.files));
        }}
      >
        <input
          ref={arquivoRef}
          type="file"
          accept="image/*,video/*"
          multiple
          hidden
          data-testid="chat-attach-input"
          onChange={(e) => {
            const lista = Array.from(e.target.files ?? []);
            e.target.value = '';
            void adicionarArquivos(lista);
          }}
        />
        <button
          type="button"
          onClick={() => arquivoRef.current?.click()}
          disabled={streamState.isStreaming || modelLoading}
          className="p-1.5 rounded-lg shrink-0 cursor-pointer disabled:opacity-30 disabled:cursor-default"
          style={{ color: 'var(--color-text-tertiary)' }}
          title={t('chat.attach.button')}
          aria-label={t('chat.attach.button')}
          data-testid="chat-attach"
        >
          <Paperclip size={16} />
        </button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={(e) => {
            // Print colado (Win+Shift+S) vira anexo; texto colado segue normal.
            const arquivos = Array.from(e.clipboardData.files).filter((f) => tipoDoArquivo(f) !== null);
            if (!arquivos.length) return;
            e.preventDefault();
            void adicionarArquivos(arquivos);
          }}
          placeholder={
            streamState.isStreaming && !isCurrentChatStreaming
              ? t('chat.input.busyElsewhere')
              : selectedModel
                ? t('chat.input.placeholder')
                : t('chat.input.pickModel', { shortcut: appShortcut('k') })
          }
          rows={1}
          className="flex-1 bg-transparent outline-none resize-none text-sm leading-relaxed"
          style={{ color: 'var(--color-text)', maxHeight: '200px' }}
          disabled={streamState.isStreaming || modelLoading}
        />
        {streamState.isStreaming ? (
          <button
            onClick={stopStreaming}
            className="p-2 rounded-xl transition-colors shrink-0 cursor-pointer"
            style={{ background: 'var(--color-error)', color: 'var(--color-on-accent)' }}
            title={t('chat.input.stop')}
            aria-label={t('chat.input.stop')}
          >
            <Square size={16} />
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <MicButton
              state={speechState}
              onClick={handleMicClick}
              disabled={micDisabled}
              reason={micReason}
            />
            <button
              onClick={() => void sendMessage()}
              disabled={
                streamState.isStreaming ||
                (!input.trim() && anexos.length === 0) ||
                anexos.some((a) => a.preparando) ||
                modelLoading ||
                !selectedModel
              }
              title={selectedModel ? t('chat.input.send') : t('chat.input.pickModel', { shortcut: appShortcut('k') })}
              aria-label={t('chat.input.send')}
              className="p-2 rounded-xl transition-colors shrink-0 cursor-pointer disabled:opacity-30 disabled:cursor-default"
              style={{
                background: input.trim() || anexos.length ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                color: input.trim() || anexos.length ? 'white' : 'var(--color-text-tertiary)',
              }}
            >
              <Send size={16} />
            </button>
          </div>
        )}
      </div>
      <div className="flex items-center justify-center mt-2 text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
        <span>
          <kbd className="font-mono">Enter</kbd> {t('chat.input.enterToSend')} &middot;{' '}
          <kbd className="font-mono">Shift+Enter</kbd> {t('chat.input.shiftEnterNewLine')}
        </span>
      </div>
    </div>
  );
}
