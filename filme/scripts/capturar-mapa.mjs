// Mapa do Brasil do Lumen (abstenção, neutro) inteiro, por estado e por município, fundo transparente-friendly.
import { chromium } from 'playwright-core';
const OUT = new URL('../public/lumen/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const p = await b.newPage({ viewport: { width: 1440, height: 1700 }, colorScheme: 'dark', deviceScaleFactor: 2 });
await p.goto('https://falkyria-lumen.vercel.app/eleicoes/', { waitUntil: 'networkidle', timeout: 90000 });
await p.waitForTimeout(2500);
await p.getByRole('button', { name: 'Abstenção', exact: true }).first().click();
await p.waitForTimeout(2500);
const mapa = p.locator('svg').filter({ has: p.locator('path') }).first();
let bx = await mapa.boundingBox(); console.log(bx);
await p.screenshot({ path: OUT + 'mapa_estados.png', clip: { x: bx.x, y: bx.y, width: bx.width, height: bx.height } });
await p.getByRole('button', { name: 'Municípios', exact: true }).first().click();
await p.waitForTimeout(7000);
bx = await mapa.boundingBox();
await p.screenshot({ path: OUT + 'mapa_municipios.png', clip: { x: bx.x, y: bx.y, width: bx.width, height: bx.height } });
await b.close();
