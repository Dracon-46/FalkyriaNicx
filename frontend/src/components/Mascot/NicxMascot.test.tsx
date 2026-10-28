import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { MascotMood } from '../../lib/mascot';
import { computeFrame, phasesAt, POSES, STILL_INPUT } from './mascot-geometry';
import { mascotStillSvg } from './mascot-still';
import { mascotMoodLabel, MASCOT_SIZES, NicxMascot } from './NicxMascot';

const MOODS: MascotMood[] = ['idle', 'listening', 'thinking', 'speaking', 'happy', 'error'];

const numbersIn = (s: string) => (s.match(/-?\d+(\.\d+)?(e-?\d+)?/g) ?? []).map(Number);

describe('NicxMascot', () => {
  it.each(MOODS)('renders the %s mood', (mood) => {
    const html = renderToStaticMarkup(<NicxMascot mood={mood} size="lg" />);

    expect(html).toContain('<svg');
    expect(html).toContain(`data-mood="${mood}"`);
    expect(html).toContain(`aria-label="Nicx (${mascotMoodLabel(mood)})"`);
    expect(html).toContain('width="180"');
    // Two eyes, a nucleus, and never a mouth.
    expect(html.match(/data-part="eye"/g)).toHaveLength(2);
    expect(html).toContain('data-part="orb"');
    expect(html).not.toMatch(/mouth/i);
    expect(html).not.toContain('NaN');
  });

  it('follows the size presets and hides decorative avatars from screen readers', () => {
    const html = renderToStaticMarkup(<NicxMascot size="sm" mood="idle" decorative />);

    expect(html).toContain(`width="${MASCOT_SIZES.sm}"`);
    expect(html).toContain('aria-hidden="true"');
    expect(html).not.toContain('role="img"');
    // Small avatars drop the tiny bubbles.
    expect(html).not.toContain('data-part="bubble"');
  });

  it('gives each instance its own gradient ids', () => {
    const html = renderToStaticMarkup(
      <>
        <NicxMascot mood="idle" />
        <NicxMascot mood="happy" />
      </>,
    );
    const ids = [...html.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('mascot geometry', () => {
  it.each(MOODS)('produces finite frames for %s across time, level and gaze', (mood) => {
    for (let t = 0; t < 6; t += 0.37) {
      const frame = computeFrame(POSES[mood], {
        ...STILL_INPUT,
        t,
        hop: t,
        level: (t % 1.2) / 1.2,
        gazeX: Math.sin(t),
        gazeY: Math.cos(t),
        blink: t % 1,
      });
      const values = [
        ...numbersIn(frame.root),
        ...numbersIn(frame.body),
        frame.orbR,
        frame.glowR,
        frame.shadowRx,
        ...frame.eyes.flatMap((e) => numbersIn(e.transform + e.lid)),
      ];
      expect(values.every(Number.isFinite)).toBe(true);
    }
  });

  it('shows happy arcs only when happy and droopy lids only on error', () => {
    const happy = computeFrame(POSES.happy, STILL_INPUT);
    const idle = computeFrame(POSES.idle, STILL_INPUT);
    const error = computeFrame(POSES.error, STILL_INPUT);

    expect(happy.eyes[0].happy).toBe(1);
    expect(idle.eyes[0].happy).toBe(0);
    expect(error.eyes[0].lid).not.toBe(idle.eyes[0].lid);
    expect(error.glowOpacity).toBeLessThan(idle.glowOpacity);
  });

  it('lets the nucleus drift around inside the jelly instead of sitting still', () => {
    const xs: number[] = [];
    const ys: number[] = [];
    for (let t = 0; t < 12; t += 0.5) {
      const frame = computeFrame(POSES.idle, { ...STILL_INPUT, t, ...phasesAt(t, POSES.idle) });
      xs.push(frame.coreX);
      ys.push(frame.coreY);
    }
    // It wanders both ways, but always stays well inside the body.
    expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(8);
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(4);
    expect(Math.min(...xs)).toBeGreaterThan(35);
    expect(Math.max(...xs)).toBeLessThan(65);
    expect(Math.min(...ys)).toBeGreaterThan(45);
    expect(Math.max(...ys)).toBeLessThan(70);
    // Stills catch it off-center, so a static Nicx never seems to have a nose.
    expect(Math.abs(computeFrame(POSES.idle, STILL_INPUT).coreX - 50)).toBeGreaterThan(3);
  });

  it('keeps the body inside the view box at full squash and lean', () => {
    const frame = computeFrame(POSES.happy, { ...STILL_INPUT, hop: 0, gazeX: 1, jiggle: -0.16 });
    const [a, , c, d, e, f] = numbersIn(frame.root);
    const pts = numbersIn(frame.body);
    for (let i = 0; i < pts.length; i += 2) {
      const x = a * pts[i] + c * pts[i + 1] + e;
      const y = d * pts[i + 1] + f;
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(100);
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(100);
    }
  });
});

describe('static mascot export', () => {
  it('is a standalone SVG without React or theme hooks', () => {
    const svg = mascotStillSvg();

    expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true);
    expect(svg).not.toMatch(/data-|class=|aria-|var\(/);
  });
});
