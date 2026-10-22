// Render Nicx brand icons. Usage: node render-icons.cjs <resvg_module_dir> <repo_root>
const fs = require('fs');
const path = require('path');
const { Resvg } = require(path.join(process.argv[2], 'node_modules', '@resvg', 'resvg-js'));
const repo = process.argv[3];

const mark = (rx) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">` +
  `<rect width="32" height="32" rx="${rx}" fill="#0b0b0b"/>` +
  `<path d="M9.5 24V8l13 16v-8.5" fill="none" stroke="#fcfcfb" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>` +
  `<circle cx="22.5" cy="9.5" r="3" fill="#eda100"/></svg>`;

// Horizontal lockup: mark + wordmark + "by Falkyria".
const horizontal =
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 64">` +
  `<g transform="translate(0,0) scale(2)">${mark(7).replace(/^<svg[^>]*>|<\/svg>$/g, '')}</g>` +
  `<text x="78" y="41" font-family="Segoe UI, Arial, sans-serif" font-weight="700" font-size="34" fill="#0b0b0b">Nicx</text>` +
  `<text x="80" y="58" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#6b6964">por Falkyria</text></svg>`;

function render(svg, width, out) {
  const png = new Resvg(svg, {
    fitTo: { mode: 'width', value: width },
    font: { loadSystemFonts: true },
  }).render().asPng();
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, png);
  console.log(`${out} (${width}px, ${png.length} bytes)`);
}

const pub = path.join(repo, 'frontend', 'public');
render(mark(7), 1024, path.join(process.argv[2], 'icon-1024.png'));
render(mark(0), 180, path.join(pub, 'apple-touch-icon.png'));
render(mark(7), 192, path.join(pub, 'pwa-192x192.png'));
render(mark(7), 512, path.join(pub, 'pwa-512x512.png'));
render(mark(7), 512, path.join(repo, 'assets', 'Nicx_Circular_Logo.png'));
render(horizontal, 880, path.join(repo, 'assets', 'Nicx_Horizontal_Logo.png'));
fs.writeFileSync(path.join(repo, 'assets', 'nicx-logo.svg'), mark(7) + '\n');
