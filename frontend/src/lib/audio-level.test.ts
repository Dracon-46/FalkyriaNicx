import { describe, expect, it } from 'vitest';
import { LEVEL_FPS, SilenceDetector, levelFromRms, rms, wavEnvelope } from './audio-level';

/** Build a mono WAV (PCM16 or float32) from samples in [-1, 1]. */
function makeWav(samples: number[], sampleRate: number, float = false): ArrayBuffer {
  const bytes = float ? 4 : 2;
  const data = samples.length * bytes;
  const buf = new ArrayBuffer(44 + data);
  const v = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, 'RIFF');
  v.setUint32(4, 36 + data, true);
  str(8, 'WAVE');
  str(12, 'fmt ');
  v.setUint32(16, 16, true);
  v.setUint16(20, float ? 3 : 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * bytes, true);
  v.setUint16(32, bytes, true);
  v.setUint16(34, bytes * 8, true);
  str(36, 'data');
  v.setUint32(40, data, true);
  samples.forEach((s, i) => {
    if (float) v.setFloat32(44 + i * 4, s, true);
    else v.setInt16(44 + i * 2, Math.round(s * 32767), true);
  });
  return buf;
}

describe('levels', () => {
  it('computes RMS and maps it to 0..1', () => {
    expect(rms([])).toBe(0);
    expect(rms([0.5, -0.5])).toBeCloseTo(0.5);
    expect(levelFromRms(0)).toBe(0);
    expect(levelFromRms(Number.NaN)).toBe(0);
    expect(levelFromRms(0.04)).toBeCloseTo(0.4);
    expect(levelFromRms(0.9)).toBe(1);
  });
});

describe('wavEnvelope', () => {
  const rate = 3000; // 100 samples per 30 fps frame
  const loudThenQuiet = [
    ...Array.from({ length: 300 }, (_, i) => (i % 2 ? 0.25 : -0.25)),
    ...Array.from({ length: 300 }, () => 0),
  ];

  it('reads PCM16 loudness per frame', () => {
    const env = wavEnvelope(makeWav(loudThenQuiet, rate), LEVEL_FPS);
    expect(env).not.toBeNull();
    expect(env).toHaveLength(6);
    expect(env![0]).toBeCloseTo(1); // sqrt(0.25) * 2
    expect(env![5]).toBe(0);
  });

  it('reads float32 WAV too', () => {
    const env = wavEnvelope(makeWav(loudThenQuiet, rate, true), LEVEL_FPS);
    expect(env).toHaveLength(6);
    expect(env![2]).toBeCloseTo(1);
    expect(env![3]).toBe(0);
  });

  it('rejects data that is not a WAV file', () => {
    expect(wavEnvelope(new TextEncoder().encode('wav').buffer as ArrayBuffer)).toBeNull();
    expect(wavEnvelope(new ArrayBuffer(64))).toBeNull();
  });
});

describe('SilenceDetector', () => {
  it('ends an utterance after speech and then silence', () => {
    const vad = new SilenceDetector({ silenceMs: 300, noSpeechMs: 5000 });
    expect(vad.push(0.001, 100)).toBeNull();
    expect(vad.push(0.2, 100)).toBeNull();
    expect(vad.spoke).toBe(true);
    expect(vad.push(0.001, 100)).toBeNull();
    expect(vad.push(0.001, 100)).toBeNull();
    expect(vad.push(0.001, 100)).toBe('speech-ended');
  });

  it('gives up when nobody speaks', () => {
    const vad = new SilenceDetector({ noSpeechMs: 300 });
    expect(vad.push(0.002, 100)).toBeNull();
    expect(vad.push(0.002, 100)).toBeNull();
    expect(vad.push(0.002, 100)).toBe('no-speech');
  });

  it('does not take steady background noise for speech', () => {
    const vad = new SilenceDetector({ noSpeechMs: 2000, minThreshold: 0.001 });
    let result = null;
    for (let i = 0; i < 20 && !result; i++) result = vad.push(0.004, 100);
    expect(vad.spoke).toBe(false);
    expect(result).toBe('no-speech');
  });

  it('caps a single utterance', () => {
    const vad = new SilenceDetector({ maxMs: 300 });
    expect(vad.push(0.3, 100)).toBeNull();
    expect(vad.push(0.3, 100)).toBeNull();
    expect(vad.push(0.3, 100)).toBe('speech-ended');
  });
});
