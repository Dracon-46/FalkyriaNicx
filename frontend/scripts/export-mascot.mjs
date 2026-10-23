// Export the Nicx mascot as a static SVG (and optionally a 512px PNG) into assets/.
//
//   cd frontend
//   node scripts/export-mascot.mjs [resvg_module_dir]
//
// The SVG comes straight from the React component (mascot-still.tsx), so the
// asset always matches the app. The PNG needs @resvg/resvg-js installed in
// <resvg_module_dir>/node_modules, the same helper folder render-icons.cjs uses.
import { writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const assets = resolve(frontend, '..', 'assets');

const server = await createServer({
  root: frontend,
  configFile: false,
  logLevel: 'error',
  server: { middlewareMode: true, hmr: false },
  appType: 'custom',
});
try {
  const { mascotStillSvg } = await server.ssrLoadModule('/src/components/Mascot/mascot-still.tsx');
  const svg = mascotStillSvg();
  writeFileSync(join(assets, 'nicx-mascot.svg'), `${svg}\n`, 'utf-8');
  console.log(`${join(assets, 'nicx-mascot.svg')} (${svg.length} bytes)`);

  const resvgDir = process.argv[2];
  if (resvgDir) {
    const require = createRequire(join(resolve(resvgDir), 'package.json'));
    const { Resvg } = require('@resvg/resvg-js');
    const png = new Resvg(svg, { fitTo: { mode: 'width', value: 512 } }).render().asPng();
    writeFileSync(join(assets, 'nicx-mascot.png'), png);
    console.log(`${join(assets, 'nicx-mascot.png')} (512px, ${png.length} bytes)`);
  }
} finally {
  await server.close();
}
