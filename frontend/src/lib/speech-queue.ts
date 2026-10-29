/**
 * Ordered voice playback for a reply that arrives sentence by sentence.
 *
 * Sentences are synthesized ahead of time -- the next one is being
 * synthesized while the current one plays -- but played strictly in order and
 * one at a time. Synthesis is limited (`maxParallel`, `lookahead`) because it
 * shares the CPU with the model that is still writing the reply.
 *
 * `cancel()` aborts every pending synthesis and the clip that is playing.
 */

export interface SpeechQueueOptions<Clip> {
  synthesize: (text: string, signal: AbortSignal) => Promise<Clip>;
  /** Play one clip; resolve when it ends (or when `signal` aborts), reject on failure. */
  play: (clip: Clip, signal: AbortSignal) => Promise<void>;
  /** Syntheses running at the same time (default 1). */
  maxParallel?: number;
  /** Clips synthesized ahead of the one playing (default 2). */
  lookahead?: number;
}

export type SpeechQueueResult = 'done' | 'cancelled';

interface Item<Clip> {
  text: string;
  clip?: Promise<Clip>;
}

export class SpeechQueue<Clip = Blob> {
  private readonly items: Item<Clip>[] = [];
  /** Index of the clip playing, or the next one to play. */
  private next = 0;
  /** How many items have had their synthesis started. */
  private started = 0;
  private inflight = 0;
  private closed = false;
  private cancelled = false;
  private readonly controller = new AbortController();
  private wake: (() => void) | null = null;
  private readonly maxParallel: number;
  private readonly lookahead: number;
  /** Settles once everything is played, the queue is cancelled, or a clip fails. */
  readonly finished: Promise<SpeechQueueResult>;

  constructor(private readonly options: SpeechQueueOptions<Clip>) {
    this.maxParallel = Math.max(1, options.maxParallel ?? 1);
    this.lookahead = Math.max(0, options.lookahead ?? 2);
    this.finished = this.run();
  }

  get isCancelled(): boolean {
    return this.cancelled;
  }

  /** Add a sentence to the end of the queue (ignored once closed or cancelled). */
  push(text: string): void {
    const trimmed = text.trim();
    if (!trimmed || this.closed || this.cancelled) return;
    this.items.push({ text: trimmed });
    this.pump();
    this.poke();
  }

  /** No more sentences will come; `finished` resolves after the last one plays. */
  close(): void {
    this.closed = true;
    this.poke();
  }

  cancel(): void {
    if (this.cancelled) return;
    this.cancelled = true;
    this.controller.abort();
    this.poke();
  }

  private poke(): void {
    const wake = this.wake;
    this.wake = null;
    wake?.();
  }

  /** Start as many syntheses as the limits allow, in order. */
  private pump(): void {
    while (
      !this.cancelled
      && this.started < this.items.length
      && this.inflight < this.maxParallel
      && this.started <= this.next + this.lookahead
    ) {
      this.startNext();
    }
  }

  private startNext(): Promise<Clip> {
    const item = this.items[this.started];
    this.started += 1;
    this.inflight += 1;
    const clip = this.options.synthesize(item.text, this.controller.signal);
    item.clip = clip;
    // Registered before anyone awaits the clip, so the slot is free again by
    // the time the player moves on. Errors are reported where it is awaited.
    const release = () => {
      this.inflight -= 1;
      this.pump();
    };
    clip.then(release, release);
    return clip;
  }

  private async run(): Promise<SpeechQueueResult> {
    // Let the constructor finish before the first wait.
    await Promise.resolve();
    try {
      while (!this.cancelled) {
        if (this.next >= this.items.length) {
          if (this.closed) return 'done';
          await new Promise<void>((resolve) => {
            this.wake = resolve;
          });
          continue;
        }
        const item = this.items[this.next];
        this.pump();
        // Played strictly in order: the clip needed now never waits for a slot.
        const clip = await (item.clip ?? this.startNext());
        if (this.cancelled) break;
        await this.options.play(clip, this.controller.signal);
        if (this.cancelled) break;
        this.next += 1;
        this.pump();
      }
      return 'cancelled';
    } catch (err) {
      if (this.cancelled) return 'cancelled';
      // One failure ends the reply: stop the syntheses still running.
      this.cancelled = true;
      this.controller.abort();
      throw err;
    }
  }
}
