import { describe, expect, it } from 'vitest';
import { SpeechQueue } from './speech-queue';

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

/**
 * A queue whose syntheses and playbacks are finished by hand, with a log of
 * what happened and when.
 */
function harness(options: { maxParallel?: number; lookahead?: number } = {}) {
  const log: string[] = [];
  const syntheses = new Map<string, ReturnType<typeof deferred<string>>>();
  const signals: AbortSignal[] = [];
  const plays = new Map<string, ReturnType<typeof deferred<void>>>();
  let playing = 0;
  let maxPlaying = 0;
  let synthesizing = 0;
  let maxSynthesizing = 0;

  const queue = new SpeechQueue<string>({
    ...options,
    synthesize: (text, signal) => {
      log.push(`synth:${text}`);
      signals.push(signal);
      synthesizing += 1;
      maxSynthesizing = Math.max(maxSynthesizing, synthesizing);
      const d = deferred<string>();
      syntheses.set(text, d);
      return d.promise.finally(() => {
        synthesizing -= 1;
      });
    },
    play: (clip, signal) => {
      log.push(`play:${clip}`);
      playing += 1;
      maxPlaying = Math.max(maxPlaying, playing);
      const d = deferred<void>();
      plays.set(clip, d);
      signal.addEventListener('abort', () => d.resolve());
      return d.promise.finally(() => {
        playing -= 1;
        log.push(`end:${clip}`);
      });
    },
  });

  const synthesized = async (text: string) => {
    syntheses.get(text)!.resolve(`clip(${text})`);
    await tick();
  };
  const ended = async (text: string) => {
    plays.get(`clip(${text})`)!.resolve();
    await tick();
  };
  return {
    queue,
    log,
    signals,
    synthesized,
    ended,
    syntheses,
    stats: () => ({ maxPlaying, maxSynthesizing }),
  };
}

describe('SpeechQueue', () => {
  it('plays in order, one at a time, even when syntheses finish out of order', async () => {
    const h = harness({ maxParallel: 2 });
    h.queue.push('a');
    h.queue.push('b');
    h.queue.push('c');
    h.queue.close();

    await h.synthesized('b');
    expect(h.log).not.toContain('play:clip(b)');
    await h.synthesized('a');
    expect(h.log.filter((l) => l.startsWith('play:'))).toEqual(['play:clip(a)']);

    await h.synthesized('c');
    await h.ended('a');
    await h.ended('b');
    await h.ended('c');

    await expect(h.queue.finished).resolves.toBe('done');
    expect(h.log.filter((l) => !l.startsWith('synth:'))).toEqual([
      'play:clip(a)', 'end:clip(a)', 'play:clip(b)', 'end:clip(b)', 'play:clip(c)', 'end:clip(c)',
    ]);
    expect(h.stats().maxPlaying).toBe(1);
  });

  it('synthesizes the next sentence while the current one plays, within the limits', async () => {
    const h = harness();
    for (const s of ['a', 'b', 'c', 'd', 'e']) h.queue.push(s);

    // One synthesis at a time by default.
    expect(h.log).toEqual(['synth:a']);
    await h.synthesized('a');
    expect(h.log).toEqual(['synth:a', 'synth:b', 'play:clip(a)']);
    await h.synthesized('b');
    await h.synthesized('c');
    // Two clips ready ahead of the one playing: no more until it ends.
    expect(h.log).toEqual(['synth:a', 'synth:b', 'play:clip(a)', 'synth:c']);
    await h.ended('a');
    expect(h.log.slice(-3)).toEqual(['end:clip(a)', 'synth:d', 'play:clip(b)']);
    expect(h.stats().maxSynthesizing).toBe(1);
  });

  it('waits for more sentences until it is closed', async () => {
    const h = harness();
    let settled = false;
    void h.queue.finished.then(() => {
      settled = true;
    });
    h.queue.push('a');
    await h.synthesized('a');
    await h.ended('a');
    expect(settled).toBe(false);

    h.queue.push('b');
    await h.synthesized('b');
    expect(h.log).toContain('play:clip(b)');
    h.queue.close();
    await h.ended('b');
    await expect(h.queue.finished).resolves.toBe('done');
  });

  it('cancel() aborts pending syntheses and the clip playing, and plays nothing more', async () => {
    const h = harness();
    h.queue.push('a');
    h.queue.push('b');
    h.queue.push('c');
    await h.synthesized('a');
    expect(h.log).toContain('play:clip(a)');

    h.queue.cancel();
    expect(h.signals.every((s) => s.aborted)).toBe(true);
    await tick();
    expect(h.log).toContain('end:clip(a)');

    // A synthesis that still answers is never played.
    await h.synthesized('b');
    h.queue.push('d');
    await expect(h.queue.finished).resolves.toBe('cancelled');
    expect(h.log.filter((l) => l.startsWith('play:'))).toEqual(['play:clip(a)']);
    expect(h.log).not.toContain('synth:d');
  });

  it('a failed synthesis ends the queue with that error', async () => {
    const h = harness();
    h.queue.push('a');
    h.queue.push('b');
    h.queue.close();
    h.syntheses.get('a')!.reject(new Error('sem voz'));
    await expect(h.queue.finished).rejects.toThrow('sem voz');
    expect(h.signals[0].aborted).toBe(true);
    expect(h.log.some((l) => l.startsWith('play:'))).toBe(false);
  });

  it('ignores blank sentences', async () => {
    const h = harness();
    h.queue.push('   ');
    h.queue.close();
    await expect(h.queue.finished).resolves.toBe('done');
    expect(h.log).toEqual([]);
  });
});
