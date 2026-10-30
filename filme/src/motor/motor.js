// @ts-nocheck
// Motor 3D do filme: um único canvas WebGL, vários "sets" (rajada, rede, logo, dados, Nicx).
// Tudo é função do tempo local do plano; nada anima sozinho (requisito do Remotion).
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { MarchingCubes } from 'three/examples/jsm/objects/MarchingCubes.js';

const W = 1920, H = 1080;
const BLUE = '#00A6FF';

// ---------- tempo ----------
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const seg = (t, a, b) => clamp01((t - a) / (b - a));
const lerp = (a, b, k) => a + (b - a) * k;
const eIO = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const eOut = (x) => 1 - Math.pow(1 - x, 3);
const eIn = (x) => x * x * x;
const eExpo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
const eSine = (x) => -(Math.cos(Math.PI * x) - 1) / 2;
const bump = (t, c, w) => Math.exp(-(((t - c) / w) ** 2));
// mola amortecida 0 -> 1 (com overshoot), x em segundos
const spring = (x, w = 14, z = 0.32) => (x <= 0 ? 0 : 1 - Math.exp(-z * w * x) * Math.cos(w * Math.sqrt(1 - z * z) * x));
function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let x = Math.imul(seed ^ (seed >>> 15), 1 | seed); x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x; return ((x ^ (x >>> 14)) >>> 0) / 4294967296; }; }
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const rdir = (R) => { const u = R() * 2 - 1, a = R() * 6.2832, s = Math.sqrt(1 - u * u); return V(s * Math.cos(a), u, s * Math.sin(a)); };

// ---------- logo oficial (desenho exato do FalkyriaLogo.tsx do site) ----------
const BIRD = 'M54 198L58 160Q66 130 100 112Q120 102 150 96L205 100L300 74L400 42L504 14L486 58L492 84L452 150L460 178L410 232Q362 268 318 302Q284 336 272 392L238 494L184 412Q138 300 118 212L100 178Q84 166 70 176Z';
const F_POLYS = [[254, 118, 278, 118, 233.6, 340, 209.6, 340], [254, 118, 560, 35.4, 560, 59.4, 254, 142], [235.2, 212, 560, 124.3, 560, 148.3, 235.2, 236]];
const EYE = [118, 130, 158, 120, 148, 139, 124, 142];
const poly = (a) => { const p = new Path2D(); p.moveTo(a[0], a[1]); for (let i = 2; i < a.length; i += 2) p.lineTo(a[i], a[i + 1]); p.closePath(); return p; };
export function logoCanvas(hpx, { bird = '#fff', eye = BLUE } = {}) {
  const s = hpx / 500, c = document.createElement('canvas');
  c.width = Math.round(480 * s); c.height = hpx;
  const g = c.getContext('2d');
  g.setTransform(s, 0, 0, s, -40 * s, 0);
  g.fillStyle = bird; g.fill(new Path2D(BIRD));
  g.globalCompositeOperation = 'destination-out';
  for (const f of F_POLYS) g.fill(poly(f));
  g.globalCompositeOperation = 'source-over';
  g.fillStyle = eye; g.fill(poly(EYE));
  return c;
}
const LOGO_ASPECT = 480 / 500;
function sampleLogo(n, seed) {
  const c = logoCanvas(320); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  const e = logoCanvas(320, { bird: 'rgba(0,0,0,0)', eye: '#fff' }).getContext('2d').getImageData(0, 0, c.width, c.height).data;
  const r = rng(seed), out = [];
  let guard = 0;
  while (out.length < n && guard++ < 3e6) {
    const x = Math.floor(r() * c.width), y = Math.floor(r() * c.height), i = (y * c.width + x) * 4;
    if (d[i + 3] > 140) out.push({ x: x / c.height - LOGO_ASPECT / 2, y: 0.5 - y / c.height, eye: e[i + 3] > 140 });
  }
  return out;
}

// recortes reais das telas do Lumen: [arquivo, x0, y0, x1, y1] em frações da imagem
const RECORTES = [
  ['contratacoes', 0.065, 0.415, 0.935, 0.585], ['contratacoes', 0.065, 0.6, 0.495, 0.89], ['contratacoes', 0.505, 0.6, 0.935, 0.89],
  ['contratacoes', 0.065, 0.26, 0.935, 0.35], ['economia', 0.065, 0.345, 0.935, 0.49], ['economia', 0.065, 0.345, 0.205, 0.49],
  ['economia', 0.21, 0.345, 0.35, 0.49], ['economia', 0.355, 0.345, 0.495, 0.49], ['conformidade', 0.065, 0.42, 0.935, 0.545],
  ['conformidade', 0.505, 0.555, 0.935, 0.99], ['conformidade', 0.065, 0.555, 0.495, 0.82], ['home', 0.065, 0.075, 0.6, 0.18],
  ['home', 0.065, 0.205, 0.5, 0.45], ['home', 0.5, 0.205, 0.935, 0.45], ['mapa_estados', 0, 0, 1, 1],
];

export async function criarMotor(canvas, urls) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H, false);
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.setClearColor(0x000000, 1);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, W / H, 0.05, 400);
  const pxScale = () => H / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
  const blueLin = new THREE.Color(BLUE);
  const cBlue = (k) => [blueLin.r * k, blueLin.g * k, blueLin.b * k];
  const cWhite = (k) => [k, k, k];
  const R = rng(20261030);
  const all = [];
  const add = (o) => { scene.add(o); all.push(o); return o; };

  // ---------- fundo volumétrico ----------
  const bgMat = new THREE.ShaderMaterial({
    depthTest: false, depthWrite: false,
    uniforms: { uTime: { value: 0 }, uLight: { value: new THREE.Vector2(0.5, 0.5) }, uInt: { value: 0 }, uBeam: { value: 0 }, uBlue: { value: new THREE.Color(BLUE) }, uRes: { value: new THREE.Vector2(W, H) }, uGrid: { value: 0 } },
    vertexShader: 'void main(){ gl_Position = vec4(position.xy, 0.9999, 1.0); }',
    fragmentShader: `
      uniform float uTime, uInt, uBeam, uGrid; uniform vec2 uLight, uRes; uniform vec3 uBlue;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
        return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
      float fbm(vec2 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 5; i++){ s += a*n(p); p = p*2.03 + 1.7; a *= 0.5; } return s; }
      void main(){
        vec2 asp = vec2(uRes.x/uRes.y, 1.0);
        vec2 p = (gl_FragCoord.xy/uRes - 0.5) * asp;
        vec2 L = (uLight - 0.5) * asp;
        vec2 d = p - L; float r = length(d) + 1e-4; float a = atan(d.y, d.x + 1e-5);
        float beams = pow(n(vec2(a*7.0, uTime*0.10)), 3.0)*0.65 + pow(n(vec2(a*19.0 + 3.0, -uTime*0.07)), 4.0)*0.5;
        float fog = fbm(p*1.7 + vec2(uTime*0.025, -uTime*0.018));
        float glow = exp(-r*r*3.2);
        vec3 col = uBlue * (glow*0.16 + beams*exp(-r*1.5)*uBeam*0.32) * (0.45 + 0.9*fog);
        col += uBlue * fog * fog * 0.022 * (1.0 - 0.6*r);
        vec2 g = abs(fract(p * 9.0) - 0.5);
        float grid = (1.0 - smoothstep(0.0, 0.03, min(g.x, g.y))) * uGrid * exp(-r * 1.2);
        col += uBlue * grid * 0.35;
        gl_FragColor = vec4(col * uInt * 0.62, 1.0);
      }`,
  });
  const bgQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bgMat);
  bgQuad.frustumCulled = false; bgQuad.renderOrder = -1000; scene.add(bgQuad);

  // ---------- pontos ----------
  function makePoints(n, { depthTest = true } = {}) {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(n * 3), size = new Float32Array(n), bright = new Float32Array(n), white = new Float32Array(n);
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
    g.setAttribute('aBright', new THREE.BufferAttribute(bright, 1));
    g.setAttribute('aWhite', new THREE.BufferAttribute(white, 1));
    const m = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, depthTest, blending: THREE.AdditiveBlending,
      uniforms: { uColor: { value: new THREE.Color(BLUE) }, uScale: { value: 1483 }, uOpacity: { value: 1 } },
      vertexShader: `
        attribute float aSize, aBright, aWhite; uniform float uScale; varying float vB, vW;
        void main(){
          vec4 mv = modelViewMatrix * vec4(position, 1.0); float d = -mv.z;
          float ps = aSize * uScale / max(d, 0.05); float a = aBright;
          if (ps < 1.4) { a *= ps / 1.4; ps = 1.4; }
          ps = min(ps, 140.0);
          a *= exp(-max(d - 9.0, 0.0) * 0.03);
          a *= smoothstep(0.35, 2.2, d);
          vB = a; vW = aWhite; gl_PointSize = ps * 2.0; gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uColor; uniform float uOpacity; varying float vB, vW;
        void main(){
          float r = length(gl_PointCoord - 0.5) * 2.0; if (r > 1.0) discard;
          float core = 1.0 - smoothstep(0.15, 0.5, r);
          float halo = exp(-r*r*5.0) * 0.32;
          vec3 c = mix(uColor, vec3(1.0), vW * core);
          gl_FragColor = vec4(c * (core + halo) * vB * uOpacity, 1.0);
        }`,
    });
    const p = new THREE.Points(g, m); p.frustumCulled = false;
    p.userData = { pos, size, bright, white, n };
    p.set = (i, v, s, b, w) => { pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z; size[i] = s; bright[i] = b; white[i] = w; };
    p.flush = () => { for (const k of ['position', 'aSize', 'aBright', 'aWhite']) g.attributes[k].needsUpdate = true; };
    p.clear = () => bright.fill(0);
    return add(p);
  }
  function makeLines(maxSeg) {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(maxSeg * 6), col = new Float32Array(maxSeg * 6);
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    l.frustumCulled = false;
    let n = 0;
    l.begin = () => { n = 0; };
    l.add2 = (a, b, ca, cb = ca) => { if (n >= maxSeg) return; pos.set([a.x, a.y, a.z, b.x, b.y, b.z], n * 6); col.set([ca[0], ca[1], ca[2], cb[0], cb[1], cb[2]], n * 6); n++; };
    l.end = () => { g.setDrawRange(0, n * 2); g.attributes.position.needsUpdate = true; g.attributes.color.needsUpdate = true; };
    return add(l);
  }
  const haloTex = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
    const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.12, 'rgba(160,220,255,0.9)'); gr.addColorStop(0.35, 'rgba(0,166,255,0.35)'); gr.addColorStop(1, 'rgba(0,166,255,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const mkSprite = () => add(new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false, transparent: true })));

  // ---------- logo ----------
  const logoTex = new THREE.CanvasTexture(logoCanvas(2048));
  logoTex.colorSpace = THREE.SRGBColorSpace; logoTex.anisotropy = 8;
  const logoGeo = new THREE.PlaneGeometry(LOGO_ASPECT, 1);
  const logo = new THREE.Group();
  const logoBase = new THREE.Mesh(logoGeo, new THREE.MeshBasicMaterial({ map: logoTex, transparent: true, depthWrite: false, opacity: 0, color: new THREE.Color(0.93, 0.93, 0.93) }));
  const logoSweep = new THREE.Mesh(logoGeo, new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { map: { value: logoTex }, uPos: { value: -1 }, uAmt: { value: 0 }, uBlue: { value: new THREE.Color(BLUE) } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform sampler2D map; uniform float uPos, uAmt; uniform vec3 uBlue; varying vec2 vUv;
      void main(){ float a = texture2D(map, vUv).a; float x = vUv.x*0.8 + vUv.y*0.45; float dx = x - uPos;
        gl_FragColor = vec4((uBlue*exp(-dx*dx*49.0)*1.4 + vec3(1.0)*exp(-dx*dx*676.0)*1.2) * a * uAmt, 1.0); }`,
  }));
  logoSweep.position.z = 0.001;
  logo.add(logoBase, logoSweep); add(logo);
  const logoHalo = mkSprite();

  // ---------- pós ----------
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
  composer.renderToScreen = false;
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new ShaderPass({
    uniforms: { tDiffuse: { value: null } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ vec4 c = texture2D(tDiffuse, vUv); gl_FragColor = vec4(clamp(c.rgb, 0.0, 6.0), 1.0); }',
  }));
  const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.75, 0.5, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const accum = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType });
  const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const accMat = new THREE.ShaderMaterial({
    transparent: true, depthTest: false, depthWrite: false,
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
    uniforms: { map: { value: null }, uW: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: 'uniform sampler2D map; uniform float uW; varying vec2 vUv; void main(){ gl_FragColor = vec4(texture2D(map, vUv).rgb * uW, 1.0); }',
  });
  const accScene = new THREE.Scene(); accScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), accMat));
  const finalMat = new THREE.ShaderMaterial({
    uniforms: { tDiffuse: { value: accum.texture }, uTime: { value: 0 }, uFlash: { value: 0 }, uFade: { value: 1 }, uCA: { value: 1 }, uGlitch: { value: 0 }, uBg: { value: new THREE.Vector3(13 / 255, 17 / 255, 23 / 255) } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime, uFlash, uFade, uCA, uGlitch; uniform vec3 uBg; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
      void main(){
        vec2 uv = vUv;
        float band = floor(uv.y * 38.0 + floor(uTime * 24.0) * 7.0);
        float gl = uGlitch * step(0.82, h(vec2(band, floor(uTime * 24.0))));
        uv.x += (h(vec2(band, 3.1)) - 0.5) * 0.06 * gl;
        vec2 c = uv - 0.5; float r = length(c * vec2(1.777, 1.0));
        vec2 off = c * r * 0.0035 * uCA + vec2(0.006 * gl, 0.0);
        vec3 col = vec3(texture2D(tDiffuse, uv + off).r, texture2D(tDiffuse, uv).g, texture2D(tDiffuse, uv - off).b);
        col *= mix(1.0, 0.62, smoothstep(0.45, 1.05, r));
        float l = dot(col, vec3(0.299, 0.587, 0.114));
        col += uBg * (1.0 - smoothstep(0.0, 0.28, l));
        col += uFlash * vec3(0.45, 0.75, 1.0);
        col = mix(uBg, col, uFade);
        col += (h(gl_FragCoord.xy + fract(uTime * 7.31) * 517.0) - 0.5) * 0.03 * (1.0 - 0.5 * l);
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  const finalScene = new THREE.Scene(); finalScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), finalMat));

  // =====================================================================
  // ELEMENTOS
  // =====================================================================
  // campo ambiente (os pontos recorrentes da marca)
  const NA = 1500;
  const amb = makePoints(NA);
  const AP = [];
  for (let i = 0; i < NA; i++) {
    const big = R() < 0.03;
    AP.push({ p: V((R() * 2 - 1) * 16, (R() * 2 - 1) * 9, lerp(10, -40, R())), w: V(0.15 + R() * 0.3, 0.12 + R() * 0.3, 0.1 + R() * 0.2), ph: R() * 6.28, s: big ? 0.16 + R() * 0.14 : 0.025 + R() * 0.045, b: big ? 0.16 + R() * 0.1 : 0.4 + R() * 0.8, tw: 0.6 + R() * 2.2, wh: R() < 0.12 ? 0.9 : 0.15 });
  }
  function drawAmbient(t, k = 1, offset = V(0, 0, 0)) {
    amb.visible = k > 0.001;
    if (!amb.visible) return;
    const tmp = V(0, 0, 0);
    for (let i = 0; i < NA; i++) {
      const a = AP[i];
      tmp.set(a.p.x + 0.35 * Math.sin(t * a.w.x + a.ph), a.p.y + 0.3 * Math.sin(t * a.w.y + a.ph * 2), a.p.z + 0.4 * Math.sin(t * a.w.z + a.ph * 3)).add(offset);
      amb.set(i, tmp, a.s, a.b * k * (0.55 + 0.45 * Math.sin(t * a.tw + a.ph) ** 2), a.wh);
    }
    amb.flush();
  }

  // rajada inicial
  const NB = 3200;
  const burst = makePoints(NB);
  const BP = []; for (let i = 0; i < NB; i++) { const d = rdir(R); d.z = Math.abs(d.z) * 1.6 + 0.2; d.normalize(); BP.push({ d, sp: 4 + Math.pow(R(), 2) * 26, s: 0.02 + R() * 0.04, b: 0.8 + R() * 1.4, w: R() < 0.25 ? 0.8 : 0.2, tw: R() * 6.28 }); }
  const core = mkSprite();
  const rings = makeLines(6 * 160);
  function ring(c, rad, f, q = camera.quaternion, segN = 160) {
    let prev = null;
    for (let j = 0; j <= segN; j++) {
      const a = j / segN * Math.PI * 2;
      const pt = V(Math.cos(a) * rad, Math.sin(a) * rad, 0).applyQuaternion(q).add(c);
      if (prev) rings.add2(prev, pt, cBlue(f));
      prev = pt;
    }
  }

  // rede (esfera de Fibonacci)
  const NODES = 260, NNET = 1700;
  const net = makePoints(NNET);
  const NP = [];
  for (let i = 0; i < NNET; i++) {
    let home;
    if (i < NODES) { const k = i + 0.5, phi = Math.acos(1 - 2 * k / NODES), th = Math.PI * (1 + Math.sqrt(5)) * k, rr = 3.5 * (0.94 + 0.12 * R()); home = V(rr * Math.sin(phi) * Math.cos(th), rr * Math.cos(phi), rr * Math.sin(phi) * Math.sin(th)); }
    else home = rdir(R).multiplyScalar(3.6 + Math.pow(R(), 0.7) * 6.5).multiply(V(1, 0.75, 1));
    NP.push({ home, node: i < NODES, ta: i < NODES ? R() * 0.9 : R() * 1.6, s: i < NODES ? 0.06 : 0.025 + R() * 0.035, b: i < NODES ? 1.6 : 0.5 + R() * 0.6, tw: R() * 6.28 });
  }
  const EDGES = [];
  {
    const seen = new Set();
    for (let i = 0; i < NODES; i++) {
      const d = []; for (let j = 0; j < NODES; j++) if (j !== i) d.push([NP[i].home.distanceToSquared(NP[j].home), j]);
      d.sort((a, b) => a[0] - b[0]);
      for (let k = 0; k < 3; k++) { const j = d[k][1], key = i < j ? `${i}-${j}` : `${j}-${i}`; if (seen.has(key)) continue; seen.add(key); EDGES.push({ a: i, b: j, te: 0.15 + R() * 1.9 }); }
    }
  }
  const netLines = makeLines(EDGES.length + 10);
  const netPos = (i, t) => { const h = NP[i].home, a = t * 0.16, c = Math.cos(a), s = Math.sin(a); return V(h.x * c + h.z * s, h.y + 0.08 * Math.sin(t * 0.7 + NP[i].tw), -h.x * s + h.z * c); };
  function drawNet(t, { build = 1, alpha = 1 } = {}) {
    net.visible = netLines.visible = true;
    const P = [];
    for (let i = 0; i < NNET; i++) {
      const p = NP[i]; const v = netPos(i, t); P.push(v);
      const k = eOut(seg(build, p.ta * 0.5, p.ta * 0.5 + 0.35));
      net.set(i, v, p.s, p.b * k * alpha * (0.7 + 0.3 * Math.sin(t * 2.3 + p.tw) ** 2) * (p.node ? 1 + 1.6 * bump(build, p.ta * 0.5 + 0.1, 0.12) : 1), p.node ? 0.55 : 0.15);
    }
    net.flush();
    netLines.begin();
    for (const e of EDGES) {
      const k = eOut(seg(build, e.te * 0.55, e.te * 0.55 + 0.3)); if (k <= 0) continue;
      const a = P[e.a], b = P[e.b];
      const f = 0.34 * alpha * (1 + 2 * bump(build, e.te * 0.55 + 0.28, 0.1));
      netLines.add2(a, a.clone().lerp(b, k), cBlue(f), cBlue(f * 0.7));
    }
    netLines.end();
    return P;
  }

  // partículas que montam a logo
  const NL = 2600;
  const lp = makePoints(NL);
  const logoPts = sampleLogo(NL, 7);
  const LPp = []; for (let i = 0; i < NL; i++) LPp.push({ from: rdir(R).multiplyScalar(2 + R() * 7), arc: rdir(R).multiplyScalar(1.4), st: R() * 0.35, tw: R() * 6.28, out: rdir(R), outR: 0.6 + R() * 2.2 });

  // dados do Lumen: fragmentos reais
  const loader = new THREE.TextureLoader();
  const texCache = {};
  for (const name of new Set(RECORTES.map((r) => r[0]))) {
    const t = await loader.loadAsync(urls[name]);
    t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
    texCache[name] = t;
  }
  const fragMat = (tex, r) => {
    const t = tex.clone(); t.needsUpdate = true;
    t.offset.set(r[1], 1 - r[4]); t.repeat.set(r[3] - r[1], r[4] - r[2]);
    return new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.DoubleSide,
      uniforms: { map: { value: t }, uOp: { value: 0 }, uGlow: { value: 0 }, uBlue: { value: new THREE.Color(BLUE) } },
      vertexShader: 'uniform sampler2D map; varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `uniform sampler2D map; uniform float uOp, uGlow; uniform vec3 uBlue; varying vec2 vUv;
        void main(){ vec3 c = texture2D(map, vUv).rgb; float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
          c = mix(c, vec3(l) * vec3(0.8, 0.95, 1.12), 0.3) * 1.25;
          vec2 e = min(vUv, 1.0 - vUv); float edge = 1.0 - smoothstep(0.0, 0.012, min(e.x * 2.0, e.y));
          gl_FragColor = vec4(c * uOp + uBlue * (edge * 1.5 + uGlow) * uOp, uOp); }`,
    });
  };
  const NF = 30, COLS = 6, ROWS = 5;
  const frags = [];
  const cellW = 2.75, cellH = 1.6;
  for (let i = 0; i < NF; i++) {
    const rc = i === 14 ? RECORTES[14] : RECORTES[i % RECORTES.length];
    const tex = texCache[rc[0]];
    const aspect = ((rc[3] - rc[1]) * tex.image.width) / ((rc[4] - rc[2]) * tex.image.height);
    let w = cellW * 0.92, h = w / aspect; if (h > cellH * 0.88) { h = cellH * 0.88; w = h * aspect; }
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), fragMat(tex, rc));
    add(m);
    const col = i % COLS, row = Math.floor(i / COLS);
    frags.push({ m, grid: V((col - (COLS - 1) / 2) * cellW, ((ROWS - 1) / 2 - row) * cellH, 0), chaos: V((R() * 2 - 1) * 9, (R() * 2 - 1) * 5.5, -R() * 9 + 1.5), rot: V((R() - 0.5) * 2.4, (R() - 0.5) * 2.4, (R() - 0.5) * 1.2), spin: V((R() - 0.5) * 0.6, (R() - 0.5) * 0.8, (R() - 0.5) * 0.4), st: R() * 0.6, map: rc[0] === 'mapa_estados' });
  }
  const gridLines = makeLines(200);

  // ---------- Nicx ----------
  const envScene = new THREE.Scene(); envScene.background = new THREE.Color(0x010204);
  {
    const mk = (w, h, col, k, pos) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(k), side: THREE.DoubleSide })); m.position.set(...pos); m.lookAt(0, 0, 0); envScene.add(m); };
    mk(3.2, 0.9, '#ffffff', 2.4, [0, 7, 2]); mk(1.6, 9, BLUE, 3.2, [-7, 0, 1]); mk(1.6, 9, BLUE, 2.2, [7, 1, -2]);
    mk(1.0, 1.0, '#ffffff', 3.0, [3.5, 2, 7]); mk(12, 1.4, '#06365c', 1.2, [0, -6, 0]); mk(4, 1, '#bfe6ff', 1.5, [-3, 3, -7]);
  }
  const envTex = new THREE.PMREMGenerator(renderer).fromScene(envScene, 0.035).texture;
  const slimeMat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color('#bfeaff'), metalness: 0, roughness: 0.13, transmission: 1, thickness: 2.4, ior: 1.36,
    attenuationColor: new THREE.Color('#0a8fe0'), attenuationDistance: 0.85, clearcoat: 1, clearcoatRoughness: 0.03,
    envMap: envTex, envMapIntensity: 1.5, iridescence: 0.22, iridescenceIOR: 1.25, specularIntensity: 1,
    emissive: new THREE.Color('#00456e'), emissiveIntensity: 0.7, sheen: 0.4, sheenColor: new THREE.Color(BLUE), sheenRoughness: 0.35,
  });
  const SC = 2.6;
  const slime = new MarchingCubes(80, slimeMat, false, false, 110000);
  slime.isolation = 30; slime.scale.setScalar(SC); add(slime);
  const keyL = new THREE.DirectionalLight(0xffffff, 1.6); keyL.position.set(3, 6, 6); scene.add(keyL);
  const rimL = new THREE.PointLight(new THREE.Color(BLUE), 22, 12, 2); scene.add(rimL);
  const BALLS = []; for (let i = 0; i < 10; i++) BALLS.push({ lag: [0, 0.05, 0.1, 0.16, 0.23, 0.3, 0.08, 0.13, 0.36, 0.42][i], r: (i < 6 ? 0.26 : 0.4) + R() * 0.26, w: [0.7 + R() * 0.8, 0.6 + R() * 0.9, 0.5 + R() * 0.8], ph: [R() * 6.28, R() * 6.28, R() * 6.28], dir: rdir(R), str: i >= 8 ? 0.32 + R() * 0.12 : 0.6 + R() * 0.25 });
  const sparks = makePoints(180, { depthTest: false });
  const SPp = []; for (let i = 0; i < 180; i++) SPp.push({ d: rdir(R), r: 0.12 + Math.pow(R(), 0.6) * 0.62, w: 0.4 + R() * 1.2, ph: R() * 6.28, s: 0.02 + R() * 0.03, b: 0.8 + R() * 1.4 });
  const nicxCore = mkSprite(), nicxHalo = mkSprite();
  const NN = 2400;
  const np = makePoints(NN);
  const NPp = []; for (let i = 0; i < NN; i++) NPp.push({ lane: (R() * 2 - 1), y: (R() * 2 - 1) * 3.2, z: (R() * 2 - 1) * 2.5, sp: 0.7 + R() * 0.8, delay: R() * 0.35, orbR: 1.3 + R() * 2.2, orbW: (2.2 + R() * 2.5) * (R() < 0.5 ? -1 : 1), orbP: R() * 6.28, tilt: (R() - 0.5) * 1.6, tilt2: (R() - 0.5) * 1.2, d: rdir(R), dr: 1.5 + R() * 3.5, s: 0.022 + R() * 0.03, b: 0.8 + R() * 1.2, tw: R() * 6.28, lag: 0.03 + R() * 0.8, wh: R() < 0.25 ? 0.7 : 0.2 });

  function drawSlime(C, t, { form = 1, split = 0, stretchFrom = null, curious = 0, lobe = V(0, 0, 0) }) {
    slime.visible = form > 0.002;
    if (!slime.visible) return;
    slime.position.copy(C);
    slime.reset();
    for (let i = 0; i < BALLS.length; i++) {
      const b = BALLS[i];
      const o = V(b.r * Math.sin(t * b.w[0] + b.ph[0]), b.r * 0.85 * Math.cos(t * b.w[1] + b.ph[1]), b.r * Math.sin(t * b.w[2] + b.ph[2]));
      if (stretchFrom) o.add(stretchFrom(b.lag));
      if (i === 0 && curious > 0) o.lerp(lobe, curious);
      o.addScaledVector(b.dir, split * 1.6);
      const str = b.str * form * (1 - 0.55 * split);
      const l = (v) => Math.min(0.9, Math.max(0.1, 0.5 + v / (2 * SC)));
      slime.addBall(l(o.x), l(o.y), l(o.z), str, 12);
    }
    slime.update();
    rimL.position.copy(C).add(V(-1.5, 1.2, -2.2));
  }
  function drawInner(C, t, life) {
    sparks.visible = nicxCore.visible = nicxHalo.visible = life > 0.001;
    if (!sparks.visible) return;
    const tmp = V(0, 0, 0);
    for (let i = 0; i < SPp.length; i++) {
      const sp = SPp[i]; const a = t * sp.w + sp.ph;
      tmp.copy(sp.d).applyAxisAngle(V(0, 1, 0), a * 0.6).applyAxisAngle(V(1, 0, 0), a * 0.25).multiplyScalar(sp.r * (1 + 0.15 * Math.sin(a * 1.3))).add(C);
      sparks.set(i, tmp, sp.s, sp.b * life * (0.4 + 0.6 * Math.sin(a * 2.0) ** 2), 0.5);
    }
    sparks.flush();
    nicxCore.position.copy(C).add(V(0.05 * Math.sin(t * 1.3), 0.06 * Math.sin(t * 1.7) - 0.05, 0.25));
    nicxCore.scale.setScalar(1.15 * (1 + 0.12 * Math.sin(t * 3.1))); nicxCore.material.opacity = 0.95 * life; nicxCore.material.color.setRGB(1.6, 1.6, 1.6);
    nicxHalo.position.copy(C).add(V(0, 0, -1.2)); nicxHalo.scale.setScalar(5.5); nicxHalo.material.opacity = 0.2 * life;
  }

  // =====================================================================
  // SETS (cada plano chama um set com seu tempo local u)
  // =====================================================================
  const look = (pos, target, fov = 40, roll = 0) => ({ pos, target, fov, roll });
  const post = { flash: 0, ca: 1, glitch: 0, fade: 1 };
  const bgSet = (int, beam, L = [0.5, 0.5], grid = 0) => { bgMat.uniforms.uInt.value = int; bgMat.uniforms.uBeam.value = beam; bgMat.uniforms.uLight.value.set(L[0], L[1]); bgMat.uniforms.uGrid.value = grid; };
  const project = (v) => { const p = v.clone().project(camera); return [p.x * 0.5 + 0.5, p.y * 0.5 + 0.5]; };

  const SETS = {
    // um ponto acende e explode num túnel de luz
    rajada(u) {
      const C = V(0, 0, 0);
      const ign = eOut(seg(u, 0.05, 0.4)) * (1 + 0.25 * Math.sin(u * 60) * (1 - seg(u, 0.2, 0.45)));
      core.visible = true; core.position.copy(C);
      const ex = u - 0.45;
      core.scale.setScalar(lerp(0.4, 1.3, ign) + (ex > 0 ? 6 * bump(ex, 0.04, 0.08) : 0));
      core.material.opacity = ign * (ex > 0 ? Math.max(0.25, 1 - seg(ex, 0.1, 0.8)) : 1);
      core.material.color.setRGB(1.8, 1.8, 1.8);
      burst.visible = true;
      for (let i = 0; i < NB; i++) {
        const p = BP[i];
        const k = ex > 0 ? (1 - Math.exp(-ex * 2.6)) / 2.6 : 0; // rampa: rápido -> lento
        const v = p.d.clone().multiplyScalar(k * p.sp);
        burst.set(i, v, p.s, ex > 0 ? p.b * (1 + 2 * bump(ex, 0.05, 0.08)) * (0.6 + 0.4 * Math.sin(u * 3 + p.tw) ** 2) : 0, p.w);
      }
      burst.flush();
      rings.visible = true; rings.begin();
      if (ex > 0) for (let r = 0; r < 2; r++) { const kk = seg(ex, r * 0.1, r * 0.1 + 0.9); if (kk > 0 && kk < 1) ring(C, lerp(0.2, 7, eOut(kk)), 1.1 * (1 - kk)); }
      rings.end();
      drawAmbient(u + 3, seg(u, 0.5, 1.2) * 0.8);
      bgSet(0.15 + 0.5 * (ex > 0 ? Math.exp(-ex * 1.5) : ign * 0.3), 0.6, [0.5, 0.5]);
      post.flash = ex > 0 ? 0.45 * bump(ex, 0.02, 0.06) : 0; post.ca = 1 + (ex > 0 ? 6 * Math.exp(-ex * 6) : 0);
      const z = 6 - (ex > 0 ? 2.2 * (1 - Math.exp(-ex * 1.8)) : 0);
      return look(V(0, 0, z), C, 40, ex > 0 ? 0.08 * Math.sin(ex * 2) : 0);
    },
    // rede: close lateral, plano aberto e voo através
    rede(u0, { cam = 'aberto', c0 = 0 } = {}) {
      const t = u0 + 2;
      const u = u0 - c0; // tempo da câmera dentro do plano
      const P = drawNet(t, { build: u0 * 1.25 });
      drawAmbient(t, 0.9);
      bgSet(0.45, 0.35, [0.5, 0.55]);
      post.ca = 1;
      if (cam === 'close') {
        const k = u;
        const yaw = 0.25 * k + (u > 0.95 ? eIn(seg(u, 0.95, 1.2)) * 1.4 : 0); // chicote no fim
        const pos = V(Math.sin(0.4 + 0.25 * k) * 4.6, 0.6 - 0.3 * k, Math.cos(0.4 + 0.25 * k) * 4.6);
        const tgt = pos.clone().add(V(-Math.cos(yaw), -0.15, Math.sin(yaw) - 0.9).normalize().multiplyScalar(3));
        return look(pos, tgt, 30, 0.05);
      }
      if (cam === 'aberto') { const k = eExpo(seg(u, 0, 1.4)); return look(V(1.2 * (1 - k), 0.3, lerp(19, 11.5, k)), V(0, 0, 0), 40, -0.04 * (1 - k)); }
      // voo: atravessa a rede até o centro
      const k = eIn(seg(u, 0, 1.5));
      return look(V(0.4 * (1 - k), 0.2 * (1 - k), lerp(11.5, 0.6, k)), V(0, 0, -3), lerp(40, 58, k), 0.12 * k);
    },
    // a rede implode na logo e a logo se assenta (u=0 implosão; 0.6 impacto)
    logo(u, { final = false } = {}) {
      const H0 = final ? 3.2 : 2.9, C = V(0, final ? 0.75 : 0.65, 0);
      const imp = 0.6;
      lp.visible = true;
      const tmp = V(0, 0, 0);
      const solid = final ? eOut(seg(u, 0.02, 0.12)) : eOut(seg(u, imp - 0.02, imp + 0.1));
      for (let i = 0; i < NL; i++) {
        const p = LPp[i], g = logoPts[i];
        const tg = V(C.x + g.x * H0, C.y + g.y * H0, 0.02);
        let b, s = 0.026;
        if (!final) {
          const k = eIn(seg(u, p.st * 0.5, imp));
          tmp.copy(p.from).lerp(tg, k).addScaledVector(p.arc, Math.sin(Math.PI * k) * 0.8);
          b = (0.9 + 0.9 * k) * (1 + 2 * bump(u, imp, 0.05));
        } else {
          const kb = eOut(seg(u, 0, 0.5));
          tmp.copy(tg).addScaledVector(p.out, p.outR * (1 - kb) * 0.2 + p.outR * bump(u, 0.05, 0.12) * 0.6);
          b = 1.6 * bump(u, 0.06, 0.2) + 0.4;
        }
        b *= 1 - 0.93 * solid * (1 - 0.6 * Math.sin(u * 3.0 + p.tw * 3.0) ** 12);
        if (u > imp && !final) tmp.addScaledVector(p.out, 0.35 * bump(u, imp + 0.08, 0.12));
        lp.set(i, tmp, s, b, g.eye ? 0 : 0.55);
      }
      lp.flush();
      logo.visible = true; logo.position.copy(C);
      const pop = final ? spring(u - 0.03, 16, 0.4) : spring(u - imp, 16, 0.4);
      logo.scale.setScalar(H0 * (1.12 - 0.12 * pop) * (1 + 0.025 * seg(u, 0.8, 3)));
      logoBase.material.opacity = solid;
      logoSweep.material.uniforms.uPos.value = lerp(-0.3, 1.5, eIO(seg(u, final ? 0.5 : 1.1, final ? 1.9 : 2.3)));
      logoSweep.material.uniforms.uAmt.value = solid * 0.7;
      logoHalo.visible = true; logoHalo.position.copy(C).add(V(0, 0, -0.5)); logoHalo.scale.setScalar(7); logoHalo.material.opacity = 0.08 * solid + 0.4 * bump(u, final ? 0.04 : imp, 0.08);
      rings.visible = true; rings.begin();
      const t0 = final ? 0.02 : imp;
      for (let r = 0; r < 2; r++) { const kk = seg(u, t0 + r * 0.08, t0 + r * 0.08 + 0.8); if (kk > 0 && kk < 1) ring(C, lerp(0.6, 9, eOut(kk)), 0.9 * (1 - kk)); }
      rings.end();
      drawAmbient(u + 9, 0.7);
      const L = project(C);
      bgSet(0.55 + 0.5 * solid, 0.3 + 0.6 * solid, L);
      post.flash = 0.38 * bump(u, t0, 0.05);
      post.ca = 1 + 5 * Math.exp(-Math.max(0, u - t0) * 5) * (u > t0 - 0.02 ? 1 : 0);
      const punch = final ? 0 : 1.6 * Math.exp(-Math.max(0, u - imp) * 4) * (u > imp ? 1 : 0);
      const z = final ? lerp(10.5, 12.5, eSine(seg(u, 0, 3))) : lerp(6.5, 8.6, eOut(seg(u, 0, imp))) + punch * 0 + lerp(0, -0.9, eSine(seg(u, imp, 2.8)));
      return look(V(0, C.y * 0.2, z), V(0, C.y * 0.75, 0), 40);
    },
    // fragmentos reais do Lumen: caos -> grade -> mergulho no mapa
    dados(u) {
      gridLines.visible = true; gridLines.begin();
      for (const f of frags) {
        f.m.visible = true;
        const ko = eOut(seg(u, f.st * 0.5, f.st * 0.5 + 0.4));
        const ks = spring(u - 1.35 - f.st * 0.7, 13, 0.45);
        const drift = V(Math.sin(u * 0.9 + f.st * 9) * 0.4, Math.cos(u * 0.7 + f.st * 7) * 0.3, u * 0.6);
        const p = f.chaos.clone().add(drift).lerp(f.grid, clamp01(ks));
        f.m.position.copy(p);
        f.m.rotation.set((f.rot.x + f.spin.x * u) * (1 - clamp01(ks)), (f.rot.y + f.spin.y * u) * (1 - clamp01(ks)), (f.rot.z + f.spin.z * u) * (1 - clamp01(ks)));
        const u2 = f.m.material.uniforms; u2.uOp.value = ko * (f.map ? 1 : 1 - 0.75 * seg(u, 2.7, 3.1)); u2.uGlow.value = 0.35 * bump(u, 1.35 + f.st * 0.7 + 0.12, 0.08);
      }
      const kg = seg(u, 2.05, 2.6);
      if (kg > 0) {
        const hw = COLS * cellW / 2, hh = ROWS * cellH / 2;
        for (let c = 0; c <= COLS; c++) { const x = -hw + c * cellW; gridLines.add2(V(x, hh, 0), V(x, lerp(hh, -hh, eOut(kg)), 0), cBlue(0.45), cBlue(0.45)); }
        for (let r = 0; r <= ROWS; r++) { const y = hh - r * cellH; gridLines.add2(V(-hw, y, 0), V(lerp(-hw, hw, eOut(kg)), y, 0), cBlue(0.45), cBlue(0.45)); }
      }
      gridLines.end();
      drawAmbient(u + 14, 0.6);
      bgSet(0.4, 0.2, [0.5, 0.6], 0.5 * seg(u, 1.8, 2.6));
      post.ca = 1;
      // mergulho no fragmento do mapa (índice 14)
      const mp = frags[14].grid;
      const kd = eIn(seg(u, 2.9, 3.5));
      const base = V(Math.sin(u * 0.4) * 1.2, 0.4, lerp(15, 13.2, eOut(seg(u, 0, 2.6))));
      return look(base.clone().lerp(V(mp.x, mp.y, 1.0), kd), V(lerp(0, mp.x, kd), lerp(0, mp.y, kd), 0), lerp(42, 30, kd), 0);
    },
    // Nicx: rajada, órbita, nascimento, perseguição, divisão, curiosidade (u em s desde o início)
    nicx(u, { modo = 'heroi' } = {}) {
      const ZN = 0;
      let C = V(0, 0, ZN);
      // trajetória da perseguição
      const chase = (tt) => { const k = eIO(seg(tt, 2.5, 3.5)); return V(lerp(-2.6, 2.4, k), 0.5 * Math.sin(k * Math.PI) - 0.1 * k, 0); };
      if (modo === 'heroi') C = u < 2.5 ? V(-2.6, 0, 0).lerp(V(-2.6, 0, 0), 1) : chase(u);
      if (modo === 'heroi' && u < 2.5) C = V(-2.6, 0, 0);
      if (modo !== 'heroi') C = V(1.8, 0.1, 0);
      const form = modo === 'heroi' ? clamp01(spring(u - 1.65, 11, 0.38)) : 1;
      const split = modo === 'heroi' ? Math.sin(Math.PI * eOut(seg(u, 3.55, 4.35))) * (u < 4.35 ? 1 : 0) : 0;
      const curious = modo === 'heroi' ? Math.sin(Math.PI * eSine(seg(u, 4.6, 6.4))) : 0;
      const lobe = V(-0.55, 0.25, 0.75);
      const conv = modo === 'converge' ? u : -1;
      const formC = conv >= 0 ? 1 - eIn(seg(conv, 0.2, 1.2)) : form;
      drawSlime(C, u + 20, { form: formC, split, curious, stretchFrom: modo === 'heroi' ? (lag) => chase(u - lag).sub(chase(u)) : null, lobe });
      const life = clamp01(spring(u - 1.5, 10, 0.5)) * (1 - seg(u, 3.5, 3.7) * (u < 4.3 ? 1 : 0) * 0.85) * (conv >= 0 ? 1 - seg(conv, 0.2, 1.0) : 1);
      drawInner(C, u + 20, modo === 'heroi' ? life : formC);
      // partículas
      np.visible = true;
      const tmp = V(0, 0, 0);
      const coreP = modo === 'heroi' ? V(-2.6, 0, 0) : C;
      for (let i = 0; i < NN; i++) {
        const p = NPp[i];
        let b = 0, s = p.s, w = p.wh;
        if (modo === 'heroi') {
          if (u < 0.8) { // rajada atravessando a tela
            const k = seg(u, p.delay, p.delay + 0.55 / p.sp);
            tmp.set(lerp(-16, 9, k) + p.lane * 2, p.y * (1 - 0.5 * k), p.z + 3 * (1 - k));
            b = p.b * Math.sin(Math.PI * k) * 2.2; s = p.s * 1.4;
          } else if (u < 1.9) { // órbita em volta do núcleo
            const k = eOut(seg(u, 0.7, 1.2));
            const a = (u - 0.7) * p.orbW + p.orbP;
            const r = lerp(p.orbR * 2.2, p.orbR, k) * (1 - 0.65 * eIn(seg(u, 1.5, 1.9)));
            tmp.set(Math.cos(a) * r, Math.sin(a) * r * Math.sin(p.tilt), Math.sin(a) * r * Math.cos(p.tilt)).applyAxisAngle(V(0, 0, 1), p.tilt2).add(coreP);
            b = p.b * k * (1 - eIn(seg(u, 1.6, 1.95)));
          } else if (u < 3.55) { // rastro da perseguição
            const lagged = chase(u - p.lag * 0.6).add(p.d.clone().multiplyScalar(0.15 + p.lag * 0.4));
            tmp.copy(lagged);
            const speed = chase(u).distanceTo(chase(u - 0.2));
            b = p.b * (1 - p.lag) * clamp01(speed * 1.5) * 1.2 * (i % 3 === 0 ? 1 : 0);
            w = 0.4;
          } else { // divisão e recomposição
            const k = Math.sin(Math.PI * eOut(seg(u, 3.55, 4.4)));
            tmp.copy(C).addScaledVector(p.d, k * p.dr * 0.7);
            b = p.b * k * 1.3 * (i % 2 === 0 ? 1 : 0);
            if (u > 4.4) { const a = u * p.orbW * 0.25 + p.orbP; tmp.set(Math.cos(a) * p.orbR * 1.1, Math.sin(a) * p.orbR * 0.35 * Math.sin(p.tilt), Math.sin(a) * p.orbR * 0.8).add(C); b = p.b * 0.35 * (i % 4 === 0 ? 1 : 0); }
          }
        } else if (modo === 'divide') {
          const a = u * p.orbW * 0.25 + p.orbP; tmp.set(Math.cos(a) * p.orbR * 1.1, Math.sin(a) * p.orbR * 0.35 * Math.sin(p.tilt), Math.sin(a) * p.orbR * 0.8).add(C); b = p.b * 0.35 * (i % 4 === 0 ? 1 : 0);
        } else { // converge: espiral até um ponto
          const k = eIn(seg(conv, 0.1 + p.delay, 2.4 + p.delay));
          const a = p.orbP + conv * p.orbW * 0.6 + k * 8;
          const r = (p.orbR * 1.6 + 1.5) * (1 - k);
          tmp.set(Math.cos(a) * r, Math.sin(a) * r * 0.6, Math.sin(a) * r * 0.5).add(V(lerp(C.x, 0, eIO(seg(conv, 0, 1.6))), lerp(C.y, 0.3, eIO(seg(conv, 0, 1.6))), 0));
          b = p.b * (0.5 + 1.2 * k) * (1 - seg(conv, 2.9, 3.2));
          s = p.s * (1 - 0.5 * k);
        }
        np.set(i, tmp, s, b, w);
      }
      np.flush();
      // anéis de interação no momento de curiosidade
      rings.visible = true; rings.begin();
      if (modo === 'heroi') for (let r = 0; r < 2; r++) { const kk = seg(u, 5.0 + r * 0.35, 5.0 + r * 0.35 + 1.2); if (kk > 0 && kk < 1) ring(C, lerp(1.2, 3.4, eOut(kk)), 0.5 * (1 - kk)); }
      if (conv >= 0) { // ponto final que concentra tudo
        core.visible = true; core.position.set(0, 0.3, 0);
        const kc = seg(conv, 1.5, 3.0);
        core.scale.setScalar(lerp(0.3, 2.2, eIn(kc)) * (1 - seg(conv, 3.05, 3.25)));
        core.material.opacity = kc * (1 - seg(conv, 3.05, 3.3)); core.material.color.setRGB(2, 2, 2);
      }
      rings.end();
      drawAmbient(u + 30, modo === 'converge' ? 0.6 * (1 - seg(conv, 2.6, 3.2)) : 0.7);
      const L = project(C);
      bgSet((0.35 + 0.6 * form) * (conv >= 0 ? 1 - seg(conv, 2.8, 3.3) : 1), 0.5, L);
      post.flash = modo === 'heroi' ? 0.18 * bump(u, 1.75, 0.08) + 0.12 * bump(u, 3.6, 0.06) : 0;
      post.ca = 1 + (modo === 'heroi' ? 4 * bump(u, 0.3, 0.2) + 3 * bump(u, 3.6, 0.1) : 0);
      post.fade = conv >= 0 ? 1 - 0.85 * seg(conv, 3.1, 3.3) : 1;
      // câmeras
      if (modo === 'divide') return look(V(-1.3, 0.2, 9.5), V(-1.3, 0.05, 0), 40);
      if (modo === 'converge') { const k = eIO(seg(conv, 0, 1.5)); return look(V(lerp(-1.3, 0, k), 0.25, lerp(9.5, 7.5, eIO(seg(conv, 0, 3)))), V(lerp(-1.3, 0, k), 0.25, 0), 40); }
      if (u < 0.8) return look(V(-1, 0, 8), V(0, 0, 0), 40, -0.12 * (1 - u));
      if (u < 1.6) { const a = -0.9 + 1.5 * eIO(seg(u, 0.8, 1.6)); return look(V(-2.6 + Math.sin(a) * 7, 0.6, Math.cos(a) * 7), coreP, 40, 0.06); }
      if (u < 2.5) { const k = eOut(seg(u, 1.6, 2.5)); return look(V(-2.6 + 0.6 * (1 - k), 0.1, lerp(8, 4.6, k)), coreP, 40); }
      if (u < 3.55) { const k = seg(u, 2.5, 3.55); const c = chase(u); return look(V(c.x - 1.4 + 0.6 * k, 0.4, 5.2), c.clone().add(V(0.4, 0, 0)), 38, -0.05 + 0.1 * k); }
      if (u < 4.45) return look(V(C.x - 0.4, 0.2, 6.2 - 0.6 * eOut(seg(u, 3.55, 4.4))), C, 40);
      const k = eSine(seg(u, 4.45, 6.8));
      return look(V(lerp(C.x - 0.6, C.x - 2.4, k), lerp(0.2, 0.35, k), lerp(5.6, 7.2, k)), V(lerp(C.x, C.x - 1.9, k), 0.1, 0), 40);
    },
  };

  let sampleFn = null;
  function applySet(s) {
    for (const o of all) o.visible = false;
    bgQuad.visible = true;
    post.flash = 0; post.ca = 1; post.glitch = s.glitch ?? 0; post.fade = 1;
    const cam = SETS[s.set](s.u, s.opts || {});
    camera.fov = cam.fov; camera.updateProjectionMatrix();
    camera.position.copy(cam.pos); camera.up.set(Math.sin(cam.roll), Math.cos(cam.roll), 0); camera.lookAt(cam.target); camera.updateMatrixWorld();
    for (const m of [amb, burst, net, lp, np, sparks]) m.material.uniforms.uScale.value = pxScale();
    bgMat.uniforms.uTime.value = s.tAbs;
  }

  return {
    // sample(tAbs) -> {set, u, opts, tAbs, start} ; sub = subquadros de motion blur
    render(tAbs, sample, sub = 6, fps = 30) {
      sampleFn = sample;
      renderer.setRenderTarget(accum); renderer.setClearColor(0x000000, 1); renderer.clear();
      const shutter = 0.5 / fps;
      const s0 = sample(tAbs);
      let flash = 0, ca = 0, glitch = 0, fade = 0;
      for (let k = 0; k < sub; k++) {
        let ts = tAbs - shutter * 0.5 + shutter * (sub === 1 ? 0.5 : k / (sub - 1));
        ts = Math.max(ts, s0.start); // o rastro não atravessa o corte
        const s = sample(ts);
        applySet(s);
        composer.render();
        flash += post.flash / sub; ca += post.ca / sub; glitch += post.glitch / sub; fade += post.fade / sub;
        accMat.uniforms.map.value = composer.readBuffer.texture; accMat.uniforms.uW.value = 1 / sub;
        renderer.setRenderTarget(accum); renderer.autoClear = false; renderer.render(accScene, ortho); renderer.autoClear = true;
      }
      finalMat.uniforms.uTime.value = tAbs; finalMat.uniforms.uFlash.value = flash + (s0.flash ?? 0);
      finalMat.uniforms.uCA.value = ca; finalMat.uniforms.uGlitch.value = glitch; finalMat.uniforms.uFade.value = fade * (s0.fade ?? 1);
      renderer.setRenderTarget(null); renderer.render(finalScene, ortho);
    },
  };
}
