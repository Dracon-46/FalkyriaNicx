/**
 * Loudness helpers for the voice UI: they turn audio into the 0..1 `level` the
 * mascot animates with, and tell speech from silence for hands-free mode.
 */

/** How often levels are sampled and pushed to the mascot. */
export const LEVEL_FPS = 30;
export const LEVEL_INTERVAL_MS = Math.round(1000 / LEVEL_FPS);

/** Root-mean-square of time-domain samples in [-1, 1]. */
export function rms(samples: ArrayLike<number>): number {
  const n = samples.length;
  if (n === 0) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const v = samples[i];
    sum += v * v;
  }
  return Math.sqrt(sum / n);
}

/**
 * Map an RMS value to a 0..1 level that reads well on screen. Speech sits
 * roughly between 0.01 and 0.3 RMS; a square-root curve keeps quiet speech
 * visible without pinning normal speech at 1.
 */
export function levelFromRms(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.min(1, Math.sqrt(value) * 2);
}

/**
 * Per-frame level envelope (0..1) of a WAV file, `fps` frames per second, so
 * playback can look up its loudness from `audio.currentTime` without routing
 * the sound through Web Audio. Supports 8/16/24/32-bit PCM and 32-bit float.
 * Returns null for anything it cannot read.
 */
export function wavEnvelope(buffer: ArrayBuffer, fps = LEVEL_FPS): number[] | null {
  const view = new DataView(buffer);
  const tag = (offset: number) =>
    String.fromCharCode(
      view.getUint8(offset),
      view.getUint8(offset + 1),
      view.getUint8(offset + 2),
      view.getUint8(offset + 3),
    );
  if (buffer.byteLength < 12 || tag(0) !== 'RIFF' || tag(8) !== 'WAVE') return null;

  let format = 0;
  let channels = 0;
  let sampleRate = 0;
  let bits = 0;
  let dataOffset = -1;
  let dataLength = 0;
  let offset = 12;
  while (offset + 8 <= buffer.byteLength) {
    const id = tag(offset);
    const size = view.getUint32(offset + 4, true);
    const body = offset + 8;
    if (id === 'fmt ' && body + 16 <= buffer.byteLength) {
      format = view.getUint16(body, true);
      channels = view.getUint16(body + 2, true);
      sampleRate = view.getUint32(body + 4, true);
      bits = view.getUint16(body + 14, true);
      // WAVE_FORMAT_EXTENSIBLE: the real format is the subformat GUID's head.
      if (format === 0xfffe && size >= 26 && body + 26 <= buffer.byteLength) {
        format = view.getUint16(body + 24, true);
      }
    } else if (id === 'data') {
      dataOffset = body;
      dataLength = Math.min(size, buffer.byteLength - body);
      break;
    }
    offset = body + size + (size % 2);
  }

  const bytes = bits / 8;
  const pcm = format === 1 && [8, 16, 24, 32].includes(bits);
  const float = format === 3 && bits === 32;
  if (dataOffset < 0 || channels < 1 || sampleRate < 1 || !(pcm || float)) return null;

  const frameBytes = bytes * channels;
  const totalFrames = Math.floor(dataLength / frameBytes);
  const perWindow = Math.max(1, Math.round(sampleRate / fps));
  const read = (pos: number): number => {
    if (float) return view.getFloat32(pos, true);
    if (bits === 8) return (view.getUint8(pos) - 128) / 128;
    if (bits === 16) return view.getInt16(pos, true) / 32768;
    if (bits === 24) {
      const v = view.getUint8(pos) | (view.getUint8(pos + 1) << 8) | (view.getInt8(pos + 2) << 16);
      return v / 8388608;
    }
    return view.getInt32(pos, true) / 2147483648;
  };

  const envelope: number[] = [];
  for (let start = 0; start < totalFrames; start += perWindow) {
    const end = Math.min(totalFrames, start + perWindow);
    let sum = 0;
    // Mono mixdown is unnecessary for loudness; the first channel suffices.
    for (let f = start; f < end; f++) {
      const v = read(dataOffset + f * frameBytes);
      sum += v * v;
    }
    envelope.push(levelFromRms(Math.sqrt(sum / (end - start))));
  }
  return envelope;
}

/**
 * Voice-activity detector for hands-free mode. Feed it one RMS value per
 * tick; it reports when someone spoke and then went quiet for `silenceMs`, or
 * when nobody spoke at all within `noSpeechMs`. The threshold follows the
 * room's noise floor so a fan or a noisy mic does not count as speech.
 */
export interface SilenceOptions {
  /** Quiet time after speech that ends the utterance. */
  silenceMs?: number;
  /** Give up when nobody speaks for this long. */
  noSpeechMs?: number;
  /** Hard cap on one utterance. */
  maxMs?: number;
  /** Lowest RMS counted as speech, whatever the noise floor. */
  minThreshold?: number;
  /**
   * Loud time needed before it counts as speech. A click, a key press or the
   * tail of Nicx's own voice is shorter than this.
   */
  minSpeechMs?: number;
}

export class SilenceDetector {
  private readonly opts: SilenceOptions;
  private noise = 0.005;
  private heardSpeech = false;
  private voicedMs = 0;
  private gapMs = 0;
  private quietMs = 0;
  private elapsedMs = 0;

  constructor(opts: SilenceOptions = {}) {
    this.opts = opts;
  }

  /** Returns 'speech-ended', 'no-speech' or null (keep listening). */
  push(value: number, dtMs: number): 'speech-ended' | 'no-speech' | null {
    const silenceMs = this.opts.silenceMs ?? 1300;
    const noSpeechMs = this.opts.noSpeechMs ?? 15000;
    const maxMs = this.opts.maxMs ?? 30000;
    const minSpeechMs = this.opts.minSpeechMs ?? 300;
    const threshold = Math.max(this.opts.minThreshold ?? 0.015, this.noise * 3);

    this.elapsedMs += dtMs;
    if (value > threshold) {
      this.voicedMs += dtMs;
      this.gapMs = 0;
      if (this.voicedMs >= minSpeechMs) this.heardSpeech = true;
      this.quietMs = 0;
    } else {
      // Track the noise floor only from quiet frames, slowly.
      this.noise = this.noise * 0.95 + value * 0.05;
      if (this.heardSpeech) this.quietMs += dtMs;
      // Short noises far apart never add up to speech.
      else if ((this.gapMs += dtMs) >= 500) this.voicedMs = 0;
    }

    if (this.heardSpeech && (this.quietMs >= silenceMs || this.elapsedMs >= maxMs)) {
      return 'speech-ended';
    }
    if (!this.heardSpeech && this.elapsedMs >= noSpeechMs) return 'no-speech';
    return null;
  }

  get spoke(): boolean {
    return this.heardSpeech;
  }
}
