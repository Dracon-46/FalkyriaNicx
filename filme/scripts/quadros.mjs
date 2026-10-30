// Gera quadros soltos para revisão: node scripts/quadros.mjs 1.0 6.9 15.5 ...  -> stills/q_<s>.png
import { bundle } from '@remotion/bundler';
import { renderStill, selectComposition } from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs';
const raiz = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), '..');
const serveUrl = await bundle({ entryPoint: path.join(raiz, 'src/index.ts'), onProgress: () => {} });
const composition = await selectComposition({ serveUrl, id: 'FilmeFalkyria', inputProps: { comAudio: false }, chromiumOptions: { gl: 'angle' } });
fs.mkdirSync(path.join(raiz, 'stills'), { recursive: true });
for (const s of process.argv.slice(2)) {
  const frame = Math.round(Number(s) * composition.fps);
  await renderStill({ composition, serveUrl, frame, output: path.join(raiz, 'stills', `q_${s}.png`), inputProps: { comAudio: false }, chromiumOptions: { gl: 'angle' }, timeoutInMilliseconds: 180000 });
  console.log('quadro', s);
}
