// Captura telas reais do Lumen (falkyria-lumen.vercel.app) em tema escuro. Nenhuma tela com candidatos.
import { chromium } from 'playwright-core';
const OUT = new URL('../public/lumen/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark', deviceScaleFactor: 2 });
const go = async (path) => { await p.goto('https://falkyria-lumen.vercel.app/' + path, { waitUntil: 'networkidle', timeout: 90000 }); await p.waitForTimeout(2500); };
const shot = (name, clip) => p.screenshot({ path: OUT + name + '.png', ...(clip ? { clip } : {}) });

// o mapa do Brasil sai do scripts/capturar-mapa.mjs (modo abstenção, sem candidatos)
await go('contratacoes/');
await shot('contratacoes');

await go('economia/');
await shot('economia');

await go('conformidade/');
await shot('conformidade');
await go('');
await shot('home');
await b.close();
