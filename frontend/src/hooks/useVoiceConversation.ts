import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  CONVERSATION_PHASE_LABEL,
  VoiceConversation,
  type ConversationPhase,
  type SendOutcome,
  type SpeechControls,
} from '../lib/voice-conversation';

export type { ConversationPhase, SendOutcome } from '../lib/voice-conversation';

/**
 * Hands-free voice conversation for the chat composer (see VoiceConversation):
 * listen, send on silence, read the reply aloud, listen again.
 */
export function useVoiceConversation(
  speech: SpeechControls,
  send: (text: string) => Promise<SendOutcome>,
) {
  const [phase, setPhase] = useState<ConversationPhase>('off');
  const speechRef = useRef(speech);
  speechRef.current = speech;
  const sendRef = useRef(send);
  sendRef.current = send;

  const controllerRef = useRef<VoiceConversation | null>(null);
  if (controllerRef.current === null) {
    controllerRef.current = new VoiceConversation({
      speech: () => speechRef.current,
      send: (text) => sendRef.current(text),
      onPhase: setPhase,
      notify: (message) => toast(message, { duration: 6000 }),
    });
  }
  const controller = controllerRef.current;

  // Leaving the chat ends the conversation and releases the microphone.
  useEffect(() => () => controller.stop(), [controller]);

  return {
    phase,
    active: phase !== 'off',
    label: CONVERSATION_PHASE_LABEL[phase],
    start: () => controller.start(),
    stop: () => controller.stop(),
    toggle: () => (controller.phase === 'off' ? controller.start() : controller.stop()),
  };
}
