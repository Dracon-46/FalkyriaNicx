import { useState, useCallback, useRef, useEffect } from 'react';
import { transcribeAudio, fetchSpeechHealth } from '../lib/api';
import { useMascot } from '../lib/mascot';
import {
  LEVEL_INTERVAL_MS,
  SilenceDetector,
  levelFromRms,
  rms,
  type SilenceOptions,
} from '../lib/audio-level';

export type SpeechState = 'idle' | 'recording' | 'transcribing';

export interface RecordingOptions extends SilenceOptions {
  /**
   * Hands-free mode: called once when the speaker goes quiet after talking
   * (`true`), or when nobody spoke within `noSpeechMs` (`false`). The caller
   * then stops the recording (to transcribe it) or cancels it.
   */
  onSilence?: (heardSpeech: boolean) => void;
}

interface Meter {
  ctx: AudioContext;
  timer: ReturnType<typeof setInterval>;
}

function audioContextCtor(): typeof AudioContext | null {
  if (typeof window === 'undefined') return null;
  const w = window as typeof window & { webkitAudioContext?: typeof AudioContext };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

function micErrorMessage(err: unknown): string {
  const name = err instanceof DOMException ? err.name : '';
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'Nenhum microfone encontrado';
  if (name === 'NotReadableError') return 'O microfone está em uso por outro programa';
  return 'Acesso ao microfone negado';
}

/** Return the mascot to idle, unless someone else changed its mood meanwhile. */
function endListeningMood(): void {
  const mascot = useMascot.getState();
  if (mascot.mood === 'listening') mascot.setMood('idle');
}

export function useSpeech() {
  const [state, setState] = useState<SpeechState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const meterRef = useRef<Meter | null>(null);

  // Check if the speech backend is available, and keep checking while it is
  // not: the server may still be starting (it loads the voice models).
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = () => {
      fetchSpeechHealth()
        .then((health) => health.available)
        .catch(() => false)
        .then((ok) => {
          if (cancelled) return;
          setAvailable(ok);
          if (!ok) timer = setTimeout(check, 5000);
        });
    };
    check();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const stopMeter = useCallback(() => {
    const meter = meterRef.current;
    meterRef.current = null;
    if (meter) {
      clearInterval(meter.timer);
      meter.ctx.close().catch(() => {});
    }
    endListeningMood();
  }, []);

  const releaseStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  /**
   * Sample the mic ~30 times a second: feed the mascot's level and, in
   * hands-free mode, the silence detector. Returns false if Web Audio is
   * unavailable (recording still works, only levels and silence detection
   * do not).
   */
  const startMeter = useCallback((stream: MediaStream, opts?: RecordingOptions): boolean => {
    const Ctor = audioContextCtor();
    if (!Ctor) return false;
    try {
      const ctx = new Ctor();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      // Not connected to the speakers: we only measure, never play the mic back.
      ctx.createMediaStreamSource(stream).connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      const detector = opts?.onSilence ? new SilenceDetector(opts) : null;
      let fired = false;
      let last = performance.now();

      const timer = setInterval(() => {
        analyser.getFloatTimeDomainData(samples);
        const value = rms(samples);
        useMascot.getState().setLevel(levelFromRms(value));
        if (!detector || fired) return;
        const now = performance.now();
        const verdict = detector.push(value, now - last);
        last = now;
        if (verdict) {
          fired = true;
          opts?.onSilence?.(verdict === 'speech-ended');
        }
      }, LEVEL_INTERVAL_MS);

      meterRef.current = { ctx, timer };
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      return true;
    } catch {
      return false;
    }
  }, []);

  /** Start recording. Resolves to false (with `error` set) if it could not. */
  const startRecording = useCallback(async (opts?: RecordingOptions): Promise<boolean> => {
    setError(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microfone não suportado neste navegador');
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      const metered = startMeter(stream, opts);
      if (opts?.onSilence && !metered) {
        // Without levels there is no way to hear the speaker stop.
        releaseStream();
        setError('O modo conversa precisa de Web Audio, indisponível aqui');
        return false;
      }

      recorder.start();
      mediaRecorderRef.current = recorder;
      useMascot.getState().setMood('listening');
      setState('recording');
      return true;
    } catch (err) {
      stopMeter();
      releaseStream();
      setError(micErrorMessage(err));
      setState('idle');
      return false;
    }
  }, [startMeter, stopMeter, releaseStream]);

  const stopRecording = useCallback(async (): Promise<string> => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state !== 'recording') {
        reject(new Error('Nada sendo gravado'));
        return;
      }
      mediaRecorderRef.current = null;
      stopMeter();

      recorder.onstop = async () => {
        setState('transcribing');
        releaseStream();

        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        chunksRef.current = [];

        try {
          const result = await transcribeAudio(blob);
          setState('idle');
          resolve(result.text);
        } catch (err) {
          setState('idle');
          const msg = err instanceof Error ? err.message : 'Falha na transcrição';
          setError(msg);
          reject(err);
        }
      };

      recorder.stop();
    });
  }, [stopMeter, releaseStream]);

  /** Stop recording and throw the audio away (no transcription). */
  const cancelRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;
    stopMeter();
    if (recorder && recorder.state !== 'inactive') {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      try {
        recorder.stop();
      } catch {
        // Already stopped.
      }
    }
    chunksRef.current = [];
    releaseStream();
    setState((s) => (s === 'recording' ? 'idle' : s));
  }, [stopMeter, releaseStream]);

  // Leaving the page must not leave the microphone open.
  useEffect(() => () => cancelRecording(), [cancelRecording]);

  return {
    state,
    error,
    available,
    startRecording,
    stopRecording,
    cancelRecording,
    isRecording: state === 'recording',
    isTranscribing: state === 'transcribing',
  };
}
