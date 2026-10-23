/**
 * Pure geometry for the Nicx mascot: a cyan slime with two eyes and a blue
 * nucleus floating inside. Everything here is deterministic math (no DOM), so
 * the same frame can be rendered by React, animated imperatively, or exported
 * as a still.
 *
 * Coordinates live in a 100x100 viewBox. The body sits on the "ground" at
 * y = GROUND and is squashed, stretched and leaned by one affine transform
 * anchored at its base, so eyes, nucleus and highlights move with the jelly.
 */
import type { MascotMood } from '../../lib/mascot';

export const CX = 50;
/** Where the slime touches the floor. */
export const GROUND = 87.6;

export const EYE_Y = 51;
export const EYE_DX = 12.5;
export const EYE_RX = 4.3;
export const EYE_RY = 5.8;
/** Resting place of the nucleus: the middle of the jelly, behind the eyes. */
export const CORE_X = CX;
export const CORE_Y = 56;

/** Target values a mood eases toward. Each field is blended frame by frame. */
export interface Pose {
  /** Breathing squash/stretch amplitude (fraction of height). */
  breathe: number;
  /** Breathing speed in rad/s. */
  breatheSpeed: number;
  /** Outline wobble amplitude in viewBox units. */
  wobble: number;
  wobbleSpeed: number;
  /** Slow side-to-side lean (shear of the top relative to the base). */
  sway: number;
  /** 0..1 how much the slime does little hops on its own (idle). */
  bob: number;
  /** How much the audio level ripples the outline. */
  ripple: number;
  /** How much the audio level swells the body and nucleus. */
  pulse: number;
  /** Static stretch: positive is taller (perked up), negative is squashed. */
  stretch: number;
  /** Static vertical offset; positive sinks, negative lifts. */
  lift: number;
  /** Happy hop amplitude (0..1). */
  bounce: number;
  eyeScale: number;
  /** 1 = wide open, lower = squint (top lid comes down). */
  eyeOpen: number;
  /** 0..1 slanted, droopy lids. */
  eyeSad: number;
  /** 0..1 crossfade from round eyes to happy arcs (^ ^). */
  happyEyes: number;
  /** Eyes slide down the face (droop). */
  eyeDrop: number;
  coreGlow: number;
  coreSize: number;
  /** Size of the nucleus' figure-eight drift inside the jelly. */
  coreDrift: number;
  /** Speed of that drift, rad/s. */
  coreSpeed: number;
  /** The nucleus sinks (positive) when Nicx is sad. */
  coreDrop: number;
  /** 0..1 sparks orbiting the nucleus. */
  swirl: number;
  /** 0..1 desaturates body and nucleus. */
  dim: number;
  blush: number;
}

export const POSES: Record<MascotMood, Pose> = {
  idle: {
    breathe: 0.026, breatheSpeed: 2.0, wobble: 0.8, wobbleSpeed: 1.7, sway: 0.032, bob: 1,
    ripple: 0, pulse: 0, stretch: 0, lift: 0, bounce: 0, eyeScale: 1, eyeOpen: 1, eyeSad: 0,
    happyEyes: 0, eyeDrop: 0, coreGlow: 0.85, coreSize: 1, coreDrift: 1, coreSpeed: 0.6,
    coreDrop: 0, swirl: 0, dim: 0, blush: 0,
  },
  listening: {
    breathe: 0.018, breatheSpeed: 2.6, wobble: 0.6, wobbleSpeed: 2.2, sway: 0.012, bob: 0,
    ripple: 1.1, pulse: 0.5, stretch: 0.055, lift: -0.6, bounce: 0, eyeScale: 1.17, eyeOpen: 1,
    eyeSad: 0, happyEyes: 0, eyeDrop: -0.6, coreGlow: 1, coreSize: 1.05, coreDrift: 0.6,
    coreSpeed: 0.8, coreDrop: -1, swirl: 0, dim: 0, blush: 0,
  },
  thinking: {
    breathe: 0.016, breatheSpeed: 1.4, wobble: 1.15, wobbleSpeed: 1.1, sway: 0.022, bob: 0,
    ripple: 0, pulse: 0, stretch: 0.01, lift: 0, bounce: 0, eyeScale: 0.97, eyeOpen: 0.66,
    eyeSad: 0, happyEyes: 0, eyeDrop: 0, coreGlow: 1.3, coreSize: 1.08, coreDrift: 1.25,
    coreSpeed: 1.6, coreDrop: 0, swirl: 1, dim: 0, blush: 0,
  },
  speaking: {
    breathe: 0.015, breatheSpeed: 2.4, wobble: 0.7, wobbleSpeed: 2.0, sway: 0.018, bob: 0,
    ripple: 0.5, pulse: 1, stretch: 0.02, lift: 0, bounce: 0, eyeScale: 1.04, eyeOpen: 1,
    eyeSad: 0, happyEyes: 0, eyeDrop: 0, coreGlow: 1.05, coreSize: 1.02, coreDrift: 0.7,
    coreSpeed: 0.9, coreDrop: 0, swirl: 0, dim: 0, blush: 0,
  },
  happy: {
    breathe: 0.02, breatheSpeed: 3.0, wobble: 1.0, wobbleSpeed: 3.0, sway: 0.03, bob: 0,
    ripple: 0, pulse: 0, stretch: 0, lift: 0, bounce: 1, eyeScale: 1.05, eyeOpen: 1, eyeSad: 0,
    happyEyes: 1, eyeDrop: 0, coreGlow: 1.5, coreSize: 1.2, coreDrift: 1.1, coreSpeed: 1.4,
    coreDrop: -1, swirl: 0, dim: 0, blush: 1,
  },
  error: {
    breathe: 0.01, breatheSpeed: 1.1, wobble: 0.3, wobbleSpeed: 0.9, sway: 0.008, bob: 0,
    ripple: 0, pulse: 0, stretch: -0.09, lift: 1.2, bounce: 0, eyeScale: 0.93, eyeOpen: 0.9,
    eyeSad: 1, happyEyes: 0, eyeDrop: 2.2, coreGlow: 0.3, coreSize: 0.88, coreDrift: 0.4,
    coreSpeed: 0.3, coreDrop: 7, swirl: 0, dim: 0.65, blush: 0,
  },
};

const POSE_KEYS = Object.keys(POSES.idle) as (keyof Pose)[];

/** Ease every field of `current` toward `target` (exponential smoothing). */
export function approachPose(current: Pose, target: Pose, k: number): void {
  for (const key of POSE_KEYS) current[key] += (target[key] - current[key]) * k;
}

/** Everything that changes from frame to frame besides the pose. */
export interface FrameInput {
  /** Seconds since the mascot started living (constant-speed motions). */
  t: number;
  /**
   * Accumulated phases (rad) of the breathing, the outline wobble and the
   * nucleus drift. They are integrated over time by the animator, so a mood
   * that changes a speed never makes the motion jump.
   */
  breath: number;
  wob: number;
  drift: number;
  /** Seconds since the happy hop started. */
  hop: number;
  /** Extra vertical offset from an idle hop (negative is up). */
  bobY: number;
  /** Audio level, already smoothed, 0..1. */
  level: number;
  /** Where the eyes look, -1..1 on each axis. */
  gazeX: number;
  gazeY: number;
  /** 0 = eyes open, 1 = fully closed. */
  blink: number;
  /** 1 = full motion, 0 = reduced motion (no breathing, wobble or hops). */
  motion: number;
  /** Extra squash (pokes, hop take-off and landing), signed fraction of height. */
  jiggle: number;
  /** Small sizes get bigger eyes and nucleus so they stay legible. */
  small: boolean;
}

/** Phases a pose reaches after `t` seconds at constant speed (for stills). */
export function phasesAt(t: number, pose: Pose): Pick<FrameInput, 'breath' | 'wob' | 'drift'> {
  return { breath: t * pose.breatheSpeed, wob: t * pose.wobbleSpeed, drift: t * pose.coreSpeed };
}

export const STILL_INPUT: FrameInput = {
  t: 0.6,
  ...phasesAt(0.6, POSES.idle),
  // Stills catch the nucleus up and to the side, behind an eye, so a static
  // Nicx never seems to have a nose or a mouth.
  drift: 1.8,
  hop: 0,
  bobY: 0,
  level: 0,
  gazeX: 0,
  gazeY: 0,
  blink: 0,
  motion: 1,
  jiggle: 0,
  small: false,
};

/**
 * One idle hop, `p` from 0 to 1: crouch, jump, land with a squash, wobble.
 * Returns the lift (negative is up) and the extra squash.
 */
export function idleHop(p: number): { y: number; squash: number } {
  if (p <= 0 || p >= 1) return { y: 0, squash: 0 };
  if (p < 0.18) return { y: 0, squash: -0.075 * Math.sin((Math.PI * p) / 0.18) };
  if (p < 0.6) {
    const a = (p - 0.18) / 0.42;
    return { y: -4.6 * Math.sin(Math.PI * a), squash: 0.05 * Math.sin(Math.PI * a) };
  }
  const b = (p - 0.6) / 0.4;
  return { y: 0, squash: -0.085 * Math.exp(-b * 3.2) * Math.cos(b * Math.PI * 2.4) * (1 - b) };
}

export interface EyeFrame {
  transform: string;
  openTransform: string;
  openOpacity: number;
  lid: string;
  happy: number;
  happyTransform: string;
}

export interface Dot {
  x: number;
  y: number;
  r: number;
  o: number;
}

export interface MascotFrame {
  /** Affine transform of the whole body group (squash, stretch, lean, hop). */
  root: string;
  /** Body outline. */
  body: string;
  shadowRx: number;
  shadowOpacity: number;
  bodyStops: string[];
  coreX: number;
  coreY: number;
  orbR: number;
  glowR: number;
  glowOpacity: number;
  orbOpacity: number;
  orbStops: string[];
  orbitOpacity: number;
  swirl: Dot[];
  bubbles: Dot[];
  eyes: [EyeFrame, EyeFrame];
  blush: number;
}

export const BODY_OFFSETS = [0, 0.36, 0.74, 1];
const BODY_COLORS = ['#dcfeff', '#86ecf7', '#2fc3d9', '#0f90aa'];
const BODY_DIM = ['#e3eef0', '#a8c9cf', '#6c9ea8', '#4a7b86'];
export const ORB_OFFSETS = [0, 0.2, 0.58, 1];
/** The nucleus fades into the jelly instead of ending in a hard edge. */
export const ORB_OPACITY = [1, 0.95, 0.72, 0];
/** Hot electric-blue center fading into Falkyria's deep blue. */
const ORB_COLORS = ['#dff1ff', '#45a2ff', '#1557d0', '#1c5cab'];
const ORB_DIM = ['#e4ebf0', '#9fb3c6', '#5d7a94', '#4f6880'];

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const r2 = (v: number) => Math.round(v * 100) / 100;

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function mix(a: string, b: string, k: number): string {
  if (k <= 0.001) return a;
  const ca = hexToRgb(a);
  const cb = hexToRgb(b);
  const out = ca.map((v, i) => Math.round(v + (cb[i] - v) * k));
  return `#${out.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

/**
 * Right half of the silhouette, top to bottom: a soft dome, sides that fall
 * almost straight, and a little foot that spreads on the floor like jelly.
 * The left half is mirrored.
 */
const PROFILE: [number, number][] = [
  [60, 28.3],
  [69.6, 32.2],
  [77.6, 39],
  [83.2, 47.8],
  [86.6, 57.6],
  [87.6, 67.2],
  [86.4, 75.6],
  [86, 81.6],
  [87.7, 84.8],
  [88.2, 86.7],
  [85.6, 87.6],
  [77.5, 87.6],
  [64.5, 87.6],
];

const BASE_OUTLINE: [number, number][] = [
  [CX, 27],
  ...PROFILE,
  [CX, 87.6],
  ...PROFILE.slice().reverse().map(([x, y]): [number, number] => [2 * CX - x, y]),
];

/** Wobble pivot, roughly the body's center of mass. */
const PIVOT_Y = 64;
const BASE_ANGLES = BASE_OUTLINE.map(([x, y]) => Math.atan2(y - PIVOT_Y, x - CX));

/** Body outline points, with the jelly wobbling above a planted base. */
function bodyPoints(t: number, wob: number, wobble: number, ripple: number) {
  if (wobble <= 0.001 && ripple <= 0.001) return BASE_OUTLINE;
  return BASE_OUTLINE.map(([x, y], i): [number, number] => {
    const weight = clamp((GROUND - 3 - y) / 40, 0, 1);
    if (weight === 0) return [x, y];
    const th = BASE_ANGLES[i];
    const dx = x - CX;
    const dy = y - PIVOT_Y;
    const len = Math.hypot(dx, dy) || 1;
    const off =
      (wobble * (0.6 * Math.sin(3 * th + wob) + 0.4 * Math.sin(5 * th - wob * 1.37 + 1.3)) +
        ripple * Math.sin(6 * th - t * 9)) *
      weight;
    return [x + (dx / len) * off, y + (dy / len) * off];
  });
}

/** Closed Catmull-Rom spline through the points, as cubic Béziers. */
function closedPath(p: [number, number][]): string {
  const n = p.length;
  let d = `M${r2(p[0][0])} ${r2(p[0][1])}`;
  for (let i = 0; i < n; i++) {
    const p0 = p[(i - 1 + n) % n];
    const p1 = p[i];
    const p2 = p[(i + 1) % n];
    const p3 = p[(i + 2) % n];
    d +=
      `C${r2(p1[0] + (p2[0] - p0[0]) / 6)} ${r2(p1[1] + (p2[1] - p0[1]) / 6)} ` +
      `${r2(p2[0] - (p3[0] - p1[0]) / 6)} ${r2(p2[1] - (p3[1] - p1[1]) / 6)} ` +
      `${r2(p2[0])} ${r2(p2[1])}`;
  }
  return `${d}Z`;
}

function eyeFrame(
  side: -1 | 1,
  pose: Pose,
  input: FrameInput,
  scale: number,
): EyeFrame {
  const x = CX + side * EYE_DX + input.gazeX * 2.6;
  const y = EYE_Y + pose.eyeDrop + input.gazeY * 1.9;
  // Lid line, in eye-local units: above the eye when open, lower to squint,
  // slanted down toward the outer corner when sad.
  const base = -EYE_RY - 1.2 + (1 - pose.eyeOpen) * EYE_RY * 2 * 0.75;
  const outer = r2(base + pose.eyeSad * 3.4);
  const inner = r2(base - pose.eyeSad * 0.5);
  const left = side < 0 ? outer : inner;
  const right = side < 0 ? inner : outer;
  const lid = `-7,${left} 7,${right} 7,9 -7,9`;
  const happy = clamp(pose.happyEyes, 0, 1);
  const openSy = Math.max(0.06, (1 - input.blink * 0.94) * (1 - happy * 0.65));
  return {
    transform: `translate(${r2(x)} ${r2(y)}) scale(${r2(scale)})`,
    openTransform: `scale(${r2(1 + input.blink * 0.08)} ${r2(openSy)})`,
    openOpacity: r2(1 - happy),
    lid,
    happy: r2(happy),
    happyTransform: `scale(1 ${r2(0.35 + 0.65 * happy)})`,
  };
}

/** Compute one frame of the mascot for a pose and the live inputs. */
export function computeFrame(pose: Pose, input: FrameInput): MascotFrame {
  const { t, motion } = input;
  const level = clamp(input.level, 0, 1);

  // Happy hops: a bouncing-ball arc with a squash on every landing.
  const hopArc = Math.abs(Math.sin(Math.PI * input.hop * 1.35));
  const bounce = pose.bounce * motion;
  const hopY = -bounce * 6 * hopArc;
  const landing = Math.pow(1 - hopArc, 4);
  const up = hopY + input.bobY * motion;

  let sy =
    1 +
    pose.stretch +
    pose.breathe * motion * Math.sin(input.breath) +
    pose.pulse * level * 0.07 * motion +
    input.jiggle;
  sy *= 1 - bounce * 0.12 * landing + bounce * 0.05 * hopArc;
  const sx = 1 - (sy - 1) * 0.75;
  // Lean toward where the eyes look, plus a slow, calm sway.
  const shear = (input.gazeX * 0.045 + pose.sway * Math.sin(t * 0.8)) * motion;
  const yOff = pose.lift + up;
  const root =
    `matrix(${r2(sx * 1000) / 1000} 0 ${r2(-shear * 1000) / 1000} ${r2(sy * 1000) / 1000} ` +
    `${r2(CX - CX * sx + shear * GROUND)} ${r2(GROUND - GROUND * sy + yOff)})`;

  const body = closedPath(
    bodyPoints(t, input.wob, pose.wobble * motion, pose.ripple * level * motion),
  );

  const airborne = clamp(-up / 6, 0, 1);
  const shadowRx = r2(29.5 * sx * (1 - airborne * 0.28));
  const shadowOpacity = r2((1 - airborne * 0.45) * (1 - pose.dim * 0.2));

  const dim = clamp(pose.dim, 0, 1);
  const bodyStops = BODY_COLORS.map((c, i) => mix(c, BODY_DIM[i], dim));
  const orbStops = ORB_COLORS.map((c, i) => mix(c, ORB_DIM[i], dim));

  // The nucleus floats inside the jelly on a slow figure-eight, pulses, and
  // lags behind hops like something suspended in gel.
  const sizeBoost = input.small ? 1.15 : 1;
  const idlePulse = 0.07 * Math.sin(t * 2.3) * motion;
  const speak = pose.pulse * level;
  const drift = pose.coreDrift * motion;
  const ph = input.drift;
  const coreX = r2(CORE_X + drift * (6 * Math.sin(ph) + 1.2 * Math.sin(ph * 2.3 + 1.1)));
  const coreY = r2(
    CORE_Y +
      pose.coreDrop +
      drift * (3.6 * Math.sin(2 * ph + 0.5) + 0.8 * Math.sin(ph * 1.7)) -
      up * 0.35,
  );
  const orbR = r2(13.5 * pose.coreSize * sizeBoost * (1 + idlePulse + speak * 0.32));
  const glowR = r2(26 * pose.coreSize * (1 + idlePulse * 1.4 + speak * 0.35));
  const glowOpacity = r2(clamp(pose.coreGlow * 0.7 + speak * 0.25, 0, 1));
  const orbOpacity = r2(clamp(0.6 + pose.coreGlow * 0.4, 0, 1));

  const swirlOn = clamp(pose.swirl, 0, 1);
  const swirl: Dot[] = [0, 1, 2].map((k) => {
    const a = t * 2.6 * Math.max(motion, 0.15) + (k * Math.PI * 2) / 3;
    const ox = Math.cos(a) * 11;
    const oy = Math.sin(a) * 4.2;
    // Tilt the orbit a little so it reads as 3D.
    const tilt = -0.32;
    const depth = Math.sin(a);
    return {
      x: r2(coreX + ox * Math.cos(tilt) - oy * Math.sin(tilt)),
      y: r2(coreY + ox * Math.sin(tilt) + oy * Math.cos(tilt)),
      r: r2((1.1 - k * 0.18) * (1 + depth * 0.3)),
      o: r2(swirlOn * (0.6 + depth * 0.4)),
    };
  });

  // Tiny bubbles drifting up through the jelly.
  const bubbles: Dot[] = input.small
    ? []
    : [
        { x0: 66, off: 0.1, r: 1.5, speed: 0.11 },
        { x0: 34.5, off: 0.55, r: 1.1, speed: 0.085 },
        { x0: 60, off: 0.8, r: 0.8, speed: 0.13 },
      ].map((b) => {
        const cycle = (((t * b.speed + b.off) % 1) + 1) % 1;
        const rise = motion > 0 ? cycle : b.off;
        return {
          x: r2(b.x0 + Math.sin(t * 1.1 + b.off * 6) * 1.2 * motion),
          y: r2(82 - rise * 36),
          r: b.r,
          o: r2(Math.sin(Math.PI * rise) * 0.85),
        };
      });

  const eyeScale = pose.eyeScale * (input.small ? 1.22 : 1);
  return {
    root,
    body,
    shadowRx,
    shadowOpacity,
    bodyStops,
    coreX,
    coreY,
    orbR,
    glowR,
    glowOpacity,
    orbOpacity,
    orbStops,
    orbitOpacity: r2(swirlOn * 0.35),
    swirl,
    bubbles,
    eyes: [eyeFrame(-1, pose, input, eyeScale), eyeFrame(1, pose, input, eyeScale)],
    blush: r2(clamp(pose.blush, 0, 1)),
  };
}
