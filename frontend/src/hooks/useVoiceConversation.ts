import { useEffect, useId, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  conversationPhaseLabel,
  VoiceConversation,
  type ConversationPhase,
  type SendOutcome,
  type SpeechControls,
} from '../lib/voice-conversation';
import { useVoiceActivity } from '../lib/voice-busy';

export type { ConversationPhase, SendOutcome } from '../lib/voice-conversation';

/**
 * Hands-free voice conversation for the chat composer (see VoiceConversation):
 * listen, send on silence, read the reply aloud (sentence by sentence, while it
 * is still being written), listen again.
 */
export function useVoiceConversation(
  speech: SpeechControls,
  send: (text: string) => Promise<SendOutcome>,
  /** Abort the reply being generated when the conversation is stopped mid-reply. */
  cancel?: () => void,
) {
  const [phase, setPhase] = useState<ConversationPhase>('off');
  const speechRef = useRef(speech);
  speechRef.current = speech;
  const sendRef = useRef(send);
  sendRef.current = send;
  const cancelRef = useRef(cancel);
  cancelRef.current = cancel;

  const controllerRef = useRef<VoiceConversation | null>(null);
  if (controllerRef.current === null) {
    controllerRef.current = new VoiceConversation({
      speech: () => speechRef.current,
      send: (text) => sendRef.current(text),
      onPhase: setPhase,
      notify: (message) => toast(message, { duration: 6000 }),
      cancel: () => cancelRef.current?.(),
    });
  }
  const controller = controllerRef.current;

  // Leaving the chat ends the conversation and releases the microphone.
  useEffect(() => () => controller.stop(), [controller]);

  // While it runs, the background "Nicx, ligar" listener stays quiet.
  const owner = useId();
  const active = phase !== 'off';
  useEffect(() => {
    useVoiceActivity.getState().setConversationActive(owner, active);
  }, [owner, active]);
  useEffect(() => () => useVoiceActivity.getState().setConversationActive(owner, false), [owner]);

  return {
    phase,
    active,
    label: conversationPhaseLabel(phase),
    start: () => controller.start(),
    stop: () => controller.stop(),
    toggle: () => (controller.phase === 'off' ? controller.start() : controller.stop()),
  };
}
