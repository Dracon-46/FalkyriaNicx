import { renderToStaticMarkup } from 'react-dom/server';
import type { MascotMood } from '../../lib/mascot';
import { NicxMascot, type MascotStill } from './NicxMascot';

/**
 * A standalone SVG of the mascot (README, icons, PNG export): no React ids, no
 * CSS hooks, cropped to the slime with its shadow, light-theme colors.
 * Used by `scripts/export-mascot.mjs`; never imported by the app.
 */
export function mascotStillSvg(
  mood: MascotMood = 'idle',
  still: MascotStill = {},
  size = 512,
): string {
  const html = renderToStaticMarkup(<NicxMascot mood={mood} still={still} size={size} />);
  return html
    .replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
    .replace('viewBox="0 0 100 100"', 'viewBox="6 15.5 88 88"')
    .replace(/ (data-[a-z-]+|class|role|aria-[a-z]+|focusable)="[^"]*"/g, '')
    .replace(/nm[a-zA-Z0-9_]*-/g, 'nicx-');
}
