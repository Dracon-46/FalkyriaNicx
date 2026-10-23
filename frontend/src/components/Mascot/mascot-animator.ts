/**
 * Drives a rendered <NicxMascot> SVG imperatively, outside React, so a frame
 * never costs a re-render. All mascots on the page share one
 * requestAnimationFrame loop that only runs while at least one of them is on
 * screen and the tab is visible.
 */
import type { MascotMood } from '../../lib/mascot';
import {
  approachPose,
  computeFrame,
  idleHop,
  POSES,
  STILL_INPUT,
  type FrameInput,
  type MascotFrame,
  type Pose,
} from './mascot-geometry';

// ── Shared loop ───────────────────────────────────────────────────────

const running = new Set<MascotAnimator>();
let rafId = 0;
let timerId: ReturnType<typeof setTimeout> | 0 = 0;
let visibilityBound = false;

function stop() {
  if (rafId) cancelAnimationFrame(rafId);
  if (timerId) clearTimeout(timerId);
  rafId = 0;
  timerId = 0;
}

function loop(now: number) {
  rafId = 0;
  if (document.hidden || running.size === 0) return;
  let due = Infinity;
  for (const anim of running) due = Math.min(due, anim.tick(now));
  // Sleep until the next frame is due instead of waking on every vsync: at
  // ~30 fps that halves the main-thread wake-ups.
  const wait = due - performance.now();
  if (wait > 20) {
    timerId = setTimeout(() => {
      timerId = 0;
      rafId = requestAnimationFrame(loop);
    }, wait - 12);
  } else {
    rafId = requestAnimationFrame(loop);
  }
}

function wake() {
  if (!visibilityBound) {
    visibilityBound = true;
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stop();
      } else {
        // Coming back after a while: don't let animations jump ahead.
        for (const anim of running) anim.resetClock();
        wake();
      }
    });
  }
  if (rafId || timerId || running.size === 0 || document.hidden) return;
  rafId = requestAnimationFrame(loop);
}

// ── Shared pointer ────────────────────────────────────────────────────

const pointer = { x: 0, y: 0, at: -Infinity, version: 0 };
let pointerUsers = 0;

function onPointerMove(e: PointerEvent) {
  pointer.x = e.clientX;
  pointer.y = e.clientY;
  pointer.at = performance.now();
  pointer.version++;
}

function trackPointer(on: boolean) {
  pointerUsers += on ? 1 : -1;
  if (on && pointerUsers === 1) window.addEventListener('pointermove', onPointerMove, { passive: true });
  if (!on && pointerUsers === 0) window.removeEventListener('pointermove', onPointerMove);
}

// ── Element handles ───────────────────────────────────────────────────

interface EyeParts {
  eye: Element;
  open: Element;
  lid: Element;
  happy: Element;
}

interface Parts {
  root: Element;
  shapes: Element[];
  shadow: Element;
  bodyStops: Element[];
  orbStops: Element[];
  glow: Element;
  orb: Element;
  orbit: Element;
  swirl: Element[];
  bubbles: Element[];
  eyes: EyeParts[];
  blush: Element[];
}

function collectParts(svg: SVGSVGElement): Parts | null {
  const one = (name: string) => svg.querySelector(`[data-part="${name}"]`);
  const all = (name: string) => Array.from(svg.querySelectorAll(`[data-part="${name}"]`));
  const root = one('root');
  const shapes = all('shape');
  const shadow = one('shadow');
  const glow = one('glow');
  const orb = one('orb');
  const orbit = one('orbit');
  if (!root || shapes.length === 0 || !shadow || !glow || !orb || !orbit) return null;
  const lids = all('lid');
  const eyes = all('eye').map((eye, i) => ({
    eye,
    open: eye.querySelector('[data-part="eye-open"]')!,
    happy: eye.querySelector('[data-part="eye-happy"]')!,
    lid: lids[i],
  }));
  if (eyes.length !== 2 || eyes.some((e) => !e.open || !e.happy || !e.lid)) return null;
  return {
    root,
    shapes,
    shadow,
    bodyStops: all('body-stop'),
    orbStops: all('orb-stop'),
    glow,
    orb,
    orbit,
    swirl: all('swirl'),
    bubbles: all('bubble'),
    eyes,
    blush: all('blush'),
  };
}

/** Set an attribute only when its value changed (cheaper style invalidation). */
function setAttr(el: Element, name: string, value: string | number) {
  const v = String(value);
  if (el.getAttribute(name) !== v) el.setAttribute(name, v);
}

function applyFrame(p: Parts, f: MascotFrame) {
  setAttr(p.root, 'transform', f.root);
  for (const s of p.shapes) setAttr(s, 'd', f.body);
  setAttr(p.shadow, 'rx', f.shadowRx);
  setAttr(p.shadow, 'opacity', f.shadowOpacity);
  p.bodyStops.forEach((s, i) => setAttr(s, 'stop-color', f.bodyStops[i]));
  p.orbStops.forEach((s, i) => setAttr(s, 'stop-color', f.orbStops[i]));
  setAttr(p.glow, 'cx', f.coreX);
  setAttr(p.glow, 'cy', f.coreY);
  setAttr(p.glow, 'r', f.glowR);
  setAttr(p.glow, 'opacity', f.glowOpacity);
  setAttr(p.orb, 'cx', f.coreX);
  setAttr(p.orb, 'cy', f.coreY);
  setAttr(p.orb, 'r', f.orbR);
  setAttr(p.orb, 'opacity', f.orbOpacity);
  // Hidden parts (mostly the thinking sparks) are not worth touching.
  setAttr(p.orbit, 'opacity', f.orbitOpacity);
  if (f.orbitOpacity > 0) {
    setAttr(p.orbit, 'transform', `translate(${f.coreX} ${f.coreY}) rotate(-18)`);
  }
  p.swirl.forEach((el, i) => {
    const d = f.swirl[i];
    setAttr(el, 'opacity', d.o);
    if (d.o <= 0) return;
    setAttr(el, 'cx', d.x);
    setAttr(el, 'cy', d.y);
    setAttr(el, 'r', d.r);
  });
  p.bubbles.forEach((el, i) => {
    const d = f.bubbles[i];
    if (!d) return;
    setAttr(el, 'cx', d.x);
    setAttr(el, 'cy', d.y);
    setAttr(el, 'opacity', d.o);
  });
  p.eyes.forEach((e, i) => {
    const d = f.eyes[i];
    setAttr(e.eye, 'transform', d.transform);
    setAttr(e.open, 'transform', d.openTransform);
    setAttr(e.open, 'opacity', d.openOpacity);
    setAttr(e.lid, 'points', d.lid);
    setAttr(e.happy, 'opacity', d.happy);
    setAttr(e.happy, 'transform', d.happyTransform);
  });
  p.blush.forEach((el) => setAttr(el, 'opacity', f.blush));
}

// ── Animator ──────────────────────────────────────────────────────────

export interface AnimatorOptions {
  /** Rendered size in px; picks the frame rate and detail level. */
  size: number;
  getMood: () => MascotMood;
  /** Live audio level 0..1 (read every frame, never re-renders React). */
  getLevel: () => number;
  /** React to clicks with a jiggle and a happy squint. */
  interactive: boolean;
}

const rand = (lo: number, hi: number) => lo + Math.random() * (hi - lo);

export class MascotAnimator {
  private parts: Parts;
  private opts: AnimatorOptions;
  private pose: Pose;
  private input: FrameInput;
  private mood: MascotMood;
  private last = 0;
  private lastDraw = 0;
  private reduced = false;
  private visible = false;
  private nextBlink: number;
  private blinkStart = -1;
  private doubleBlink = false;
  private gazeTarget = { x: 0, y: 0 };
  private nextGlance = 0;
  private rect: DOMRect | null = null;
  private rectVersion = -1;
  private rectAt = 0;
  private levelAt = 0;
  private poke = -1;
  /** Idle hops: when the current one started (-1: none) and when the next is due. */
  private hopStart = -1;
  private nextHop: number;
  private settled = false;
  /** Something quick is on screen (blink, glance, mood change...). */
  private busy = true;

  constructor(parts: Parts, opts: AnimatorOptions) {
    this.parts = parts;
    this.opts = opts;
    this.mood = opts.getMood();
    this.pose = { ...POSES[this.mood] };
    // Start from the frame React rendered, so mounting never pops.
    this.input = {
      t: STILL_INPUT.t,
      breath: STILL_INPUT.breath,
      wob: STILL_INPUT.wob,
      drift: STILL_INPUT.drift,
      hop: 0,
      bobY: 0,
      level: 0,
      gazeX: 0,
      gazeY: 0,
      blink: 0,
      motion: 1,
      jiggle: 0,
      small: opts.size < 44,
    };
    this.nextBlink = this.input.t + rand(1.5, 4);
    this.nextHop = this.input.t + rand(2, 4.5);
  }

  /** Attach to the SVG; returns the cleanup function. */
  static attach(svg: SVGSVGElement, opts: AnimatorOptions): () => void {
    const parts = collectParts(svg);
    if (!parts || typeof requestAnimationFrame !== 'function') return () => {};
    const anim = new MascotAnimator(parts, opts);

    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const onMedia = () => {
      anim.reduced = !!media?.matches;
      anim.settled = false;
    };
    onMedia();
    media?.addEventListener?.('change', onMedia);

    trackPointer(true);
    const setVisible = (on: boolean) => {
      anim.visible = on;
      if (on) {
        anim.resetClock();
        running.add(anim);
        wake();
      } else {
        running.delete(anim);
      }
    };
    let observer: IntersectionObserver | null = null;
    if (typeof IntersectionObserver === 'function') {
      observer = new IntersectionObserver((entries) => {
        for (const e of entries) setVisible(e.isIntersecting);
      });
      observer.observe(svg);
    } else {
      setVisible(true);
    }

    const onPoke = () => {
      if (!opts.interactive) return;
      anim.poke = 0;
      anim.settled = false;
    };
    svg.addEventListener('pointerdown', onPoke);

    return () => {
      observer?.disconnect();
      running.delete(anim);
      trackPointer(false);
      media?.removeEventListener?.('change', onMedia);
      svg.removeEventListener('pointerdown', onPoke);
    };
  }

  resetClock() {
    this.last = 0;
    this.lastDraw = 0;
  }

  /**
   * Milliseconds between drawn frames. Slow breathing looks smooth even at
   * 15 fps (each step is a fraction of a pixel), so a calm mascot draws
   * little; blinks, glances, idle hops and mood changes get 30-40 fps, and
   * only happy hops and pokes get full speed. Small avatars go slower still.
   */
  private frameInterval(): number {
    const size = this.opts.size;
    if (this.reduced) return 66;
    if (this.mood === 'happy' || this.poke >= 0) return size >= 120 ? 16 : 25;
    // An idle hop is short and small: 40 fps (30 on medium sizes) is plenty.
    if (this.hopStart >= 0) return size >= 120 ? 25 : 33;
    if (this.busy) return size >= 120 ? 33 : size >= 48 ? 40 : 50;
    return size >= 48 ? 66 : 100;
  }

  /** Draw a frame if one is due; returns when the next one is due. */
  tick(now: number): number {
    if (!this.visible) return Infinity;
    const interval = this.frameInterval();
    if (this.lastDraw && now - this.lastDraw < interval - 2) return this.lastDraw + interval;
    this.draw(now);
    if (this.reduced && this.settled) {
      // Nothing moves until the next blink; still look for mood changes twice a second.
      const untilBlink = (this.nextBlink - this.input.t) * 1000;
      return now + Math.max(interval, Math.min(500, untilBlink));
    }
    return now + this.frameInterval();
  }

  private draw(now: number) {
    const dt = this.last ? Math.min(0.1, (now - this.last) / 1000) : 1 / 60;
    this.last = now;
    this.lastDraw = now;

    const input = this.input;
    input.t += dt;
    const t = input.t;

    // Mood changes: ease the pose toward the new target.
    const mood = this.opts.getMood();
    if (mood !== this.mood) {
      if (mood === 'happy') input.hop = 0;
      this.mood = mood;
      this.nextGlance = 0;
      this.settled = false;
    }
    const target = POSES[mood];
    const ease = this.reduced ? 1 : 1 - Math.exp(-dt * 5.5);
    approachPose(this.pose, target, ease);
    // Integrate the phases so speed changes between moods never make a jump.
    input.breath += dt * this.pose.breatheSpeed;
    input.wob += dt * this.pose.wobbleSpeed;
    input.drift += dt * this.pose.coreSpeed;
    input.motion = this.reduced ? 0 : 1;
    input.hop += dt;

    // Audio level: smooth it; when speaking without any level feed, fake a
    // gentle talking rhythm so the slime is still visibly "speaking".
    const raw = Math.min(1, Math.max(0, this.opts.getLevel()));
    if (raw > 0.01) this.levelAt = t;
    let level = raw;
    if (mood === 'speaking' && t - this.levelAt > 0.4 && !this.reduced) {
      level = 0.45 * Math.abs(Math.sin(t * 6.5)) * (0.6 + 0.4 * Math.sin(t * 1.7));
    }
    if (this.reduced) level = 0;
    input.level += (level - input.level) * (1 - Math.exp(-dt * 16));

    this.updateBlink(t);
    const glancing = this.updateGaze(t, dt, mood);
    const pokeHappy = this.updatePoke(dt);
    input.jiggle += this.updateHop(t);
    this.busy =
      glancing ||
      input.blink > 0 ||
      mood === 'thinking' ||
      mood === 'listening' ||
      mood === 'speaking' ||
      Math.abs(this.pose.eyeScale - target.eyeScale) +
        Math.abs(this.pose.stretch - target.stretch) +
        Math.abs(this.pose.happyEyes - target.happyEyes) +
        Math.abs(this.pose.eyeOpen - target.eyeOpen) +
        Math.abs(this.pose.eyeSad - target.eyeSad) >
        0.01;

    const pose =
      pokeHappy > 0
        ? {
            ...this.pose,
            happyEyes: Math.max(this.pose.happyEyes, pokeHappy),
            blush: Math.max(this.pose.blush, pokeHappy),
          }
        : this.pose;
    // Reduced motion and nothing changing: skip the DOM work entirely.
    if (this.reduced && this.settled && input.blink === 0 && pokeHappy === 0) return;
    applyFrame(this.parts, computeFrame(pose, input));
    if (this.reduced) this.settled = input.blink === 0 && pokeHappy === 0;
  }

  private updateBlink(t: number) {
    const input = this.input;
    // A quick close-open every few seconds, sometimes twice; sad eyes blink less.
    if (this.blinkStart < 0 && t >= this.nextBlink) {
      this.blinkStart = t;
    }
    if (this.blinkStart >= 0) {
      const phase = (t - this.blinkStart) / 0.16;
      if (phase >= 1) {
        input.blink = 0;
        this.blinkStart = -1;
        if (!this.doubleBlink && Math.random() < 0.22) {
          this.doubleBlink = true;
          this.nextBlink = t + 0.12;
        } else {
          this.doubleBlink = false;
          const slow = this.mood === 'error' ? 1.6 : 1;
          this.nextBlink = t + rand(2.4, 5.5) * slow;
        }
      } else {
        input.blink = Math.sin(Math.PI * phase);
      }
    }
  }

  private pointerGaze(): { x: number; y: number } | null {
    const now = performance.now();
    if (now - pointer.at > 6000) return null;
    const svg = (this.parts.root as SVGElement).ownerSVGElement;
    if (!svg) return null;
    if (!this.rect || (pointer.version !== this.rectVersion && now - this.rectAt > 150)) {
      this.rect = svg.getBoundingClientRect();
      this.rectVersion = pointer.version;
      this.rectAt = now;
    }
    const r = this.rect;
    if (r.width === 0) return null;
    const dx = pointer.x - (r.left + r.width / 2);
    const dy = pointer.y - (r.top + r.height * 0.55);
    return { x: dx / (Math.abs(dx) + 170), y: dy / (Math.abs(dy) + 170) };
  }

  /** Move the eyes toward their target; true while they are still moving. */
  private updateGaze(t: number, dt: number, mood: MascotMood): boolean {
    const input = this.input;
    let k = 7;
    if (this.reduced) {
      this.gazeTarget = { x: 0, y: mood === 'error' ? 0.5 : 0 };
      k = 50;
    } else if (mood === 'thinking') {
      // Glance around, mostly up, as if looking for the answer.
      if (t >= this.nextGlance) {
        this.gazeTarget = { x: rand(-0.85, 0.85), y: rand(-0.95, -0.3) };
        this.nextGlance = t + rand(0.6, 1.5);
      }
      k = 11;
    } else if (mood === 'error') {
      this.gazeTarget = { x: Math.sin(t * 0.7) * 0.15, y: 0.55 };
      k = 4;
    } else if (mood === 'happy') {
      this.gazeTarget = { x: 0, y: -0.15 };
    } else {
      const p = this.pointerGaze();
      if (mood === 'listening') {
        // Attentive: face the user, only nudged by the cursor.
        this.gazeTarget = { x: (p?.x ?? 0) * 0.35, y: (p?.y ?? 0) * 0.25 };
      } else if (p) {
        this.gazeTarget = p;
      } else if (t >= this.nextGlance) {
        // Nobody around: look about lazily, often back to the front.
        this.gazeTarget =
          Math.random() < 0.4 ? { x: 0, y: 0 } : { x: rand(-0.65, 0.65), y: rand(-0.35, 0.35) };
        this.nextGlance = t + rand(1.8, 4.5);
        k = 9;
      }
    }
    const a = 1 - Math.exp(-dt * k);
    const dx = this.gazeTarget.x - input.gazeX;
    const dy = this.gazeTarget.y - input.gazeY;
    input.gazeX += dx * a;
    input.gazeY += dy * a;
    return Math.abs(dx) + Math.abs(dy) > 0.02;
  }

  /**
   * Now and then an idle Nicx does a little hop (sometimes two in a row).
   * Sets the lift and returns the extra squash of take-off and landing.
   */
  private updateHop(t: number): number {
    const input = this.input;
    input.bobY = 0;
    if (this.reduced) {
      this.hopStart = -1;
      return 0;
    }
    if (this.hopStart < 0 && t >= this.nextHop) {
      if (this.pose.bob > 0.5) this.hopStart = t;
      else this.nextHop = t + rand(1.5, 3);
    }
    if (this.hopStart < 0) return 0;
    const p = (t - this.hopStart) / 0.9;
    if (p >= 1) {
      this.hopStart = -1;
      this.nextHop = t + (Math.random() < 0.22 ? 0.2 : rand(3.2, 6.5));
      return 0;
    }
    const hop = idleHop(p);
    input.bobY = hop.y * this.pose.bob;
    return hop.squash * this.pose.bob;
  }

  /** Damped squash after a click; returns how "happy-squinty" to look. */
  private updatePoke(dt: number): number {
    const input = this.input;
    if (this.poke < 0) {
      input.jiggle = 0;
      return 0;
    }
    this.poke += dt;
    const p = this.poke;
    if (p > 1.1) {
      this.poke = -1;
      input.jiggle = 0;
      return 0;
    }
    input.jiggle = this.reduced ? 0 : -0.16 * Math.exp(-p * 5) * Math.cos(p * 19);
    return p < 0.75 ? 1 : 1 - (p - 0.75) / 0.35;
  }
}
