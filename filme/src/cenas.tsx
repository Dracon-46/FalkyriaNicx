import React, { useLayoutEffect, useRef } from 'react';
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { COR, FONTE } from './estilo';

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const suave = Easing.bezier(0.16, 1, 0.3, 1);

// ---------------------------------------------------------------- texto cinético
type LetreiroProps = {
  readonly texto: string;
  readonly inicio: number; // s, local ao Sequence
  readonly fim?: number;
  readonly estilo: React.CSSProperties;
  readonly modo?: 'impacto' | 'revela' | 'digita';
  readonly espaco?: [number, number]; // letter-spacing em em: inicial -> final
  readonly passo?: number; // atraso entre letras (s)
  readonly doCentro?: boolean;
  readonly cores?: Record<number, string>; // índice da letra -> cor
};
export const Letreiro: React.FC<LetreiroProps> = ({ texto, inicio, fim = 999, estilo, modo = 'revela', espaco = [0.6, 0.3], passo = 0.025, doCentro = true, cores = {} }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (t < inicio - 0.05 || t > fim + 0.5) return null;
  const n = texto.length;
  const saida = interpolate(t, [fim, fim + 0.35], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  const ls = interpolate(t, [inicio, inicio + 1.8], espaco, { ...clamp, easing: Easing.out(Easing.exp) }) + saida * 0.08;
  return (
    <div style={{ ...estilo, letterSpacing: `${ls}em`, textIndent: estilo.textAlign === 'left' ? 0 : `${ls}em`, whiteSpace: 'pre' }}>
      {[...texto].map((ch, j) => {
        const ordem = doCentro ? Math.abs(j - (n - 1) / 2) : j;
        const t0 = inicio + ordem * passo;
        let op: number, blur: number, dy: number, sc = 1;
        if (modo === 'impacto') {
          const k = spring({ frame: (t - t0) * fps, fps, config: { damping: 14, stiffness: 220, mass: 0.6 } });
          op = interpolate(t, [t0, t0 + 0.06], [0, 1], clamp);
          sc = interpolate(k, [0, 1], [1.9, 1]);
          blur = interpolate(k, [0, 1], [14, 0], clamp);
          dy = 0;
        } else if (modo === 'digita') {
          op = t >= t0 ? 1 : 0;
          blur = 0;
          dy = 0;
        } else {
          const k = interpolate(t, [t0, t0 + 0.6], [0, 1], { ...clamp, easing: suave });
          op = k;
          blur = (1 - k) * 12;
          dy = (1 - k) * 0.35;
        }
        op *= 1 - saida;
        blur += saida * 10;
        return (
          <span key={j} style={{ display: 'inline-block', opacity: op, filter: blur > 0.05 ? `blur(${blur}px)` : undefined, translate: `0 ${dy - saida * 0.15}em`, scale: sc, color: cores[j] }}>
            {ch}
          </span>
        );
      })}
    </div>
  );
};

const marca = (px: number): React.CSSProperties => ({ fontFamily: FONTE.marca, fontWeight: 600, fontSize: px, color: COR.branco, textShadow: '0 0 28px rgba(0,166,255,.35)' });
const rotulo = (px: number, cor: string = COR.azul): React.CSSProperties => ({ fontFamily: FONTE.rotulo, fontWeight: 500, fontSize: px, color: cor });
const mono = (px: number, cor: string = COR.cinzaClaro): React.CSSProperties => ({ fontFamily: FONTE.mono, fontWeight: 500, fontSize: px, color: cor, letterSpacing: '0.08em' });
const centro = (top: number): React.CSSProperties => ({ position: 'absolute', left: 0, right: 0, top, textAlign: 'center' });

// recorte de uma imagem por frações (x0, y0, x1, y1)
const Recorte: React.FC<{ readonly src: string; readonly r: [number, number, number, number]; readonly largura: number; readonly proporcao: number; readonly style?: React.CSSProperties }> = ({ src, r, largura, proporcao, style }) => {
  const w = largura / (r[2] - r[0]);
  const h = (w / proporcao);
  const altura = h * (r[3] - r[1]);
  return (
    <div style={{ width: largura, height: altura, overflow: 'hidden', position: 'relative', ...style }}>
      <Img src={src} style={{ position: 'absolute', width: w, height: h, left: -r[0] * w, top: -r[1] * h, maxWidth: 'none' }} />
    </div>
  );
};
const P_TELA = 2880 / 1800;

// grade técnica de fundo
const Grade: React.FC<{ readonly op: number; readonly passo?: number }> = ({ op, passo = 60 }) => (
  <AbsoluteFill style={{ opacity: op, backgroundImage: `linear-gradient(rgba(0,166,255,.10) 1px, transparent 1px), linear-gradient(90deg, rgba(0,166,255,.10) 1px, transparent 1px)`, backgroundSize: `${passo}px ${passo}px`, backgroundPosition: 'center' }} />
);

// cantoneiras de interface
const Cantos: React.FC<{ readonly x: number; readonly y: number; readonly w: number; readonly h: number; readonly op: number }> = ({ x, y, w, h, op }) => {
  const c = 26;
  const s = { position: 'absolute', borderColor: 'rgba(255,255,255,.8)', borderStyle: 'solid', width: c, height: c, opacity: op } as const;
  return (
    <>
      <div style={{ ...s, left: x, top: y, borderWidth: '2px 0 0 2px' }} />
      <div style={{ ...s, left: x + w - c, top: y, borderWidth: '2px 2px 0 0' }} />
      <div style={{ ...s, left: x, top: y + h - c, borderWidth: '0 0 2px 2px' }} />
      <div style={{ ...s, left: x + w - c, top: y + h - c, borderWidth: '0 2px 2px 0' }} />
    </>
  );
};

// ---------------------------------------------------------------- Tipografia (engenharia)
export const Tipografia: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const palavras = [
    { p: 'TECNOLOGIA', a: 0, b: 0.6 },
    { p: 'ENGENHARIA', a: 0.6, b: 1.2 },
    { p: 'PRECISÃO', a: 1.2, b: 2.15 },
  ];
  const atual = palavras.find((w) => t >= w.a && t < w.b) ?? palavras[2];
  const k = t - atual.a;
  const linhas = interpolate(k, [0, 0.45], [0, 1], { ...clamp, easing: suave });
  const zoom = interpolate(k, [0, atual.b - atual.a], [1.08, 1], clamp);
  return (
    <AbsoluteFill style={{ backgroundColor: 'rgba(13,17,23,.92)' }}>
      <Grade op={0.6} passo={48} />
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
        {[0, 1, 2, 3].map((i) => (
          <line key={i} x1={i % 2 ? 1920 : 0} y1={300 + i * 160} x2={i % 2 ? 1920 - 1920 * linhas : 1920 * linhas} y2={300 + i * 160} stroke={COR.azul} strokeOpacity={0.35} strokeWidth={1} />
        ))}
        <circle cx={960} cy={540} r={330 * linhas} fill="none" stroke={COR.azul} strokeOpacity={0.25} strokeDasharray="4 10" />
        <circle cx={960} cy={540} r={200 + 40 * linhas} fill="none" stroke="#fff" strokeOpacity={0.12} />
        <text x={150} y={190} fill={COR.cinzaClaro} fontFamily={FONTE.mono} fontSize={18} letterSpacing={3}>{`0${palavras.indexOf(atual) + 1} / 03`}</text>
      </svg>
      <div style={{ ...centro(430), scale: zoom }}>
        <Letreiro key={atual.p} texto={atual.p} inicio={atual.a} fim={atual.b - 0.06} modo="impacto" espaco={[0.4, 0.1]} passo={0.018} estilo={{ ...marca(128) }} />
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- Lumen
const MapaAzul: React.FC<{ readonly style?: React.CSSProperties; readonly brilho?: number }> = ({ style, brilho = 1 }) => (
  // mapa real do Lumen (abstenção por município), tingido de azul e com fundo transparente: scripts/capturar-mapa.mjs + ffmpeg
  <Img src={staticFile('lumen/mapa_azul.png')} style={{ position: 'absolute', width: '100%', height: '100%', filter: `contrast(1.2) brightness(${1.05 * brilho}) drop-shadow(0 0 18px rgba(0,166,255,.25))`, ...style }} />
);

export const LumenMapa: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const scan = interpolate(t, [0, 0.7], [0, 100], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const z = interpolate(t, [0, 2.3], [1.0, 1.32], { ...clamp, easing: Easing.inOut(Easing.sin) });
  const tit = interpolate(t, [0.85, 1.05], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ backgroundColor: COR.grafite }}>
      <Grade op={0.7} />
      <div style={{ position: 'absolute', left: 960 - 470, top: 40, width: 940, height: 965, scale: z, translate: `${interpolate(t, [0, 2.3], [0, -120], clamp)}px ${interpolate(t, [0, 2.3], [0, 60], clamp)}px`, clipPath: `inset(0 0 ${100 - scan}% 0)`, opacity: 1 - 0.55 * tit }}>
        <MapaAzul style={{ inset: 0 }} />
      </div>
      <div style={{ position: 'absolute', left: 0, right: 0, top: `${4 + scan * 0.92}%`, height: 2, background: COR.azul, boxShadow: '0 0 24px #00A6FF', opacity: scan < 100 ? 1 : 0 }} />
      <div style={{ position: 'absolute', left: 120, top: 110 }}>
        <Letreiro texto="MUNICÍPIOS · ABSTENÇÃO" inicio={0.15} modo="digita" passo={0.02} doCentro={false} espaco={[0.18, 0.18]} estilo={{ ...mono(20, COR.texto), textAlign: 'left' }} />
        <Letreiro texto="FONTE: TSE · ELEIÇÕES 2026" inicio={0.35} modo="digita" passo={0.02} doCentro={false} espaco={[0.18, 0.18]} estilo={{ ...mono(16), textAlign: 'left', marginTop: 10 }} />
      </div>
      <Cantos x={470} y={40} w={980} h={1000} op={interpolate(t, [0.2, 0.5], [0, 0.7], clamp)} />
      <div style={centro(420)}>
        <Letreiro texto="LUMEN" inicio={0.95} modo="impacto" espaco={[0.7, 0.32]} passo={0.04} estilo={marca(190)} />
      </div>
    </AbsoluteFill>
  );
};

export const LumenNumeros: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const foco = interpolate(t, [0, 0.35], [14, 0], { ...clamp, easing: suave });
  return (
    <AbsoluteFill style={{ backgroundColor: COR.grafite, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 60, top: 250, scale: interpolate(t, [0, 0.8], [1.9, 2.1], clamp), filter: `blur(${foco}px)`, transformOrigin: '0% 30%' }}>
        <Recorte src={staticFile('lumen/contratacoes.png')} r={[0.065, 0.415, 0.935, 0.585]} largura={2400} proporcao={P_TELA} />
      </div>
      <div style={{ position: 'absolute', left: 120, bottom: 120 }}>
        <Letreiro texto="CONTRATAÇÕES PÚBLICAS · FONTE: PNCP" inicio={0.1} modo="digita" passo={0.015} doCentro={false} espaco={[0.18, 0.18]} estilo={{ ...mono(20, COR.azul), textAlign: 'left' }} />
      </div>
    </AbsoluteFill>
  );
};

export const LumenIndicadores: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cartoes: [number, number, number, number][] = [[0.065, 0.345, 0.205, 0.49], [0.21, 0.345, 0.35, 0.49], [0.355, 0.345, 0.495, 0.49], [0.5, 0.345, 0.64, 0.49]];
  return (
    <AbsoluteFill style={{ backgroundColor: COR.grafite }}>
      <Grade op={0.5} />
      {cartoes.map((r, i) => {
        const k = spring({ frame: (t - i * 0.07) * fps, fps, config: { damping: 15, stiffness: 180 } });
        return (
          <div key={i} style={{ position: 'absolute', left: 170 + i * 405, top: 360, translate: `${(1 - k) * 600}px ${(1 - k) * (i % 2 ? 40 : -40)}px`, opacity: interpolate(t, [i * 0.07, i * 0.07 + 0.12], [0, 1], clamp), rotate: `${(1 - k) * 6}deg`, boxShadow: `0 0 0 1px rgba(0,166,255,${0.25 + 0.5 * Math.exp(-((t - i * 0.07 - 0.3) ** 2) / 0.01)}), 0 30px 80px rgba(0,0,0,.6)` }}>
            <Recorte src={staticFile('lumen/economia.png')} r={r} largura={380} proporcao={P_TELA} />
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: 170, top: 270 }}>
        <Letreiro texto="ECONOMIA · INDICADORES PRINCIPAIS" inicio={0.05} modo="digita" passo={0.012} doCentro={false} espaco={[0.18, 0.18]} estilo={{ ...mono(20, COR.texto), textAlign: 'left' }} />
      </div>
      <div style={{ position: 'absolute', left: 170, top: 700 }}>
        <Letreiro texto="FONTE: BANCO CENTRAL · IBGE" inicio={0.3} modo="digita" passo={0.015} doCentro={false} espaco={[0.18, 0.18]} estilo={{ ...mono(18, COR.azul), textAlign: 'left' }} />
      </div>
    </AbsoluteFill>
  );
};

export const LumenFontes: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const fontes = ['TSE', 'PNCP', 'TESOURO NACIONAL', 'BANCO CENTRAL', 'IBGE', 'RECEITA FEDERAL', 'CVM', 'SEST'];
  const cx = 960, cy = 540;
  return (
    <AbsoluteFill style={{ backgroundColor: COR.grafite }}>
      <Grade op={0.45} />
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
        {fontes.map((_, i) => {
          const a = -Math.PI / 2 + (i / fontes.length) * Math.PI * 2;
          const x = cx + Math.cos(a) * 610, y = cy + Math.sin(a) * 330;
          const k = interpolate(t, [0.1 + i * 0.05, 0.45 + i * 0.05], [0, 1], { ...clamp, easing: suave });
          const pulso = interpolate((t * 1.4 + i * 0.13) % 1, [0, 1], [0, 1]);
          return (
            <g key={i}>
              <line x1={cx} y1={cy} x2={cx + (x - cx) * k} y2={cy + (y - cy) * k} stroke={COR.azul} strokeOpacity={0.55} strokeWidth={1.2} />
              {k >= 1 && <circle cx={cx + (x - cx) * pulso} cy={cy + (y - cy) * pulso} r={3} fill="#fff" />}
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r={interpolate(t, [0, 0.3], [0, 70], { ...clamp, easing: suave })} fill="none" stroke={COR.azul} strokeWidth={2} />
      </svg>
      {fontes.map((f, i) => {
        const a = -Math.PI / 2 + (i / fontes.length) * Math.PI * 2;
        const x = cx + Math.cos(a) * 610, y = cy + Math.sin(a) * 330;
        const op = interpolate(t, [0.35 + i * 0.05, 0.5 + i * 0.05], [0, 1], clamp);
        return (
          <div key={f} style={{ position: 'absolute', left: x, top: y, translate: '-50% -50%', opacity: op, padding: '12px 20px', border: '1px solid rgba(0,166,255,.6)', background: 'rgba(13,17,23,.9)', ...mono(19, COR.branco), whiteSpace: 'nowrap' }}>
            <span style={{ color: COR.azul }}>FONTE · </span>{f}
          </div>
        );
      })}
      <div style={{ ...centro(cy - 24) }}>
        <span style={{ ...marca(40), letterSpacing: '0.3em', opacity: interpolate(t, [0.15, 0.35], [0, 1], clamp) }}>LUMEN</span>
      </div>
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 70, textAlign: 'center' }}>
        <Letreiro texto="CADA NÚMERO COM A SUA FONTE" inicio={0.6} modo="revela" passo={0.012} espaco={[0.4, 0.28]} estilo={{ ...rotulo(22, COR.texto) }} />
      </div>
    </AbsoluteFill>
  );
};

// quadrados que somem em ordem aleatória (saída digital)
const Dissolucao: React.FC<{ readonly progresso: number }> = ({ progresso }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  useLayoutEffect(() => {
    const c = ref.current; if (!c) return;
    const g = c.getContext('2d'); if (!g) return;
    g.clearRect(0, 0, 1920, 1080);
    const cols = 48, rows = 27, w = 1920 / cols, h = 1080 / rows;
    for (let i = 0; i < cols * rows; i++) {
      const r = (Math.sin(i * 12.9898) * 43758.5453) % 1;
      const v = Math.abs(r);
      if (v < progresso) { g.fillStyle = COR.grafite; g.fillRect((i % cols) * w, Math.floor(i / cols) * h, w + 1, h + 1); }
      else if (v < progresso + 0.06) { g.fillStyle = 'rgba(0,166,255,.85)'; g.fillRect((i % cols) * w + w * 0.3, Math.floor(i / cols) * h + h * 0.3, w * 0.4, h * 0.4); }
    }
  }, [progresso]);
  return <canvas ref={ref} width={1920} height={1080} style={{ position: 'absolute', inset: 0 }} />;
};

export const LumenLema: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const itens = ['DADOS PÚBLICOS.', 'EVIDÊNCIAS.', 'TRANSPARÊNCIA.'];
  return (
    <AbsoluteFill style={{ backgroundColor: COR.grafite }}>
      <div style={{ position: 'absolute', right: -120, top: 60, width: 940, height: 965, opacity: 0.32, scale: interpolate(t, [0, 2.1], [1.05, 1.12], clamp) }}>
        <MapaAzul style={{ inset: 0 }} brilho={0.9} />
      </div>
      <Grade op={0.6} />
      <div style={{ position: 'absolute', left: 170, top: 300 }}>
        <Letreiro texto="LUMEN · UM PROJETO FALKYRIA" inicio={0} modo="digita" passo={0.015} doCentro={false} espaco={[0.3, 0.3]} estilo={{ ...rotulo(20), textAlign: 'left' }} />
        {itens.map((it, i) => (
          <div key={it} style={{ display: 'flex', alignItems: 'baseline', gap: 28, marginTop: i === 0 ? 34 : 6 }}>
            <span style={{ ...mono(22, COR.azul), opacity: interpolate(t, [0.2 + i * 0.32, 0.3 + i * 0.32], [0, 1], clamp) }}>{`0${i + 1}`}</span>
            <Letreiro texto={it} inicio={0.2 + i * 0.32} modo="impacto" doCentro={false} passo={0.02} espaco={[0.25, 0.08]} estilo={{ ...marca(84), textAlign: 'left' }} />
          </div>
        ))}
      </div>
      <Dissolucao progresso={interpolate(t, [1.7, 2.1], [0, 1.08], clamp)} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- Nicx
export const NicxTitulo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const mask = interpolate(t, [0.1, 0.7], [0, 100], { ...clamp, easing: Easing.out(Easing.exp) });
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 170, top: 360 }}>
        <Letreiro texto="UM PROJETO FALKYRIA" inicio={0.05} fim={2.0} modo="digita" passo={0.015} doCentro={false} espaco={[0.4, 0.4]} estilo={{ ...rotulo(18), textAlign: 'left' }} />
        <div style={{ clipPath: `inset(0 ${100 - mask}% 0 0)`, marginTop: 6 }}>
          <div style={{ ...marca(170), letterSpacing: '0.18em', translate: `${(1 - mask / 100) * -60}px 0`, opacity: interpolate(t, [2.0, 2.3], [1, 0], clamp) }}>NICX</div>
        </div>
        <Letreiro texto="INTELIGÊNCIA ARTIFICIAL QUE RODA NO SEU COMPUTADOR" inicio={0.55} fim={2.0} modo="revela" passo={0.008} doCentro={false} espaco={[0.3, 0.16]} estilo={{ ...rotulo(22, COR.texto), textAlign: 'left', marginTop: 10 }} />
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- Duas iniciativas
export const Divisao: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const linha = interpolate(t, [0, 0.35], [0, 1080], { ...clamp, easing: suave });
  const entra = spring({ frame: t * fps, fps, config: { damping: 18, stiffness: 140 } });
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 0, top: 0, width: 960, height: 1080, overflow: 'hidden', background: COR.grafite, translate: `${(1 - entra) * -960}px 0` }}>
        <Grade op={0.6} />
        <div style={{ position: 'absolute', left: 30, top: 80, width: 900, height: 925, scale: interpolate(t, [0, 2.8], [1, 1.07], clamp) }}>
          <MapaAzul style={{ inset: 0 }} />
        </div>
        <div style={{ position: 'absolute', left: 70, top: 64, ...rotulo(26, COR.branco), letterSpacing: '0.35em' }}>LUMEN</div>
      </div>
      <div style={{ position: 'absolute', left: 1030, top: 64, ...rotulo(26, COR.branco), letterSpacing: '0.35em', opacity: interpolate(t, [0.3, 0.6], [0, 1], clamp) }}>NICX</div>
      <div style={{ position: 'absolute', left: 959, top: 0, width: 2, height: linha, background: COR.azul, boxShadow: '0 0 20px #00A6FF' }} />
    </AbsoluteFill>
  );
};

export const MetadeLumenFecha: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const k = interpolate(t, [0, 0.7], [1, 0], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  if (k <= 0.001) return null;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 960 * (1 - k), top: 0, width: 960 * k, height: 1080, overflow: 'hidden', background: COR.grafite, opacity: 0.4 + 0.6 * k }}>
        <div style={{ position: 'absolute', left: 30 - 960 * (1 - k), top: 80, width: 900, height: 925 }}>
          <MapaAzul style={{ inset: 0 }} />
        </div>
      </div>
      <div style={{ position: 'absolute', left: 959, top: 0, width: 2, height: 1080, background: COR.azul, boxShadow: '0 0 20px #00A6FF', opacity: k }} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- textos soltos
export const Frase: React.FC<{ readonly texto: string; readonly top: number; readonly fim: number; readonly px?: number; readonly cores?: Record<number, string> }> = ({ texto, top, fim, px = 44, cores }) => (
  <AbsoluteFill>
    <div style={centro(top)}>
      <Letreiro texto={texto} inicio={0} fim={fim} modo="revela" passo={0.022} espaco={[0.55, 0.3]} estilo={{ fontFamily: FONTE.texto, fontWeight: 500, fontSize: px, color: COR.branco, textShadow: '0 0 24px rgba(0,166,255,.35)' }} cores={cores} />
    </div>
  </AbsoluteFill>
);

export const Marca: React.FC<{ readonly top: number; readonly px: number; readonly sub?: string; readonly fim?: number }> = ({ top, px, sub, fim = 999 }) => (
  <AbsoluteFill>
    <div style={centro(top)}>
      <Letreiro texto="FALKYRIA" inicio={0} fim={fim} modo="revela" passo={0.05} espaco={[1.0, 0.5]} estilo={marca(px)} />
    </div>
    {sub && (
      <div style={centro(top + px * 1.55)}>
        <Letreiro texto={sub} inicio={0.65} fim={fim} modo="revela" passo={0.014} espaco={[0.8, 0.5]} estilo={{ ...rotulo(17, COR.cinzaClaro) }} />
      </div>
    )}
  </AbsoluteFill>
);

// barra de luz que varre a tela num corte (transição por luz)
export const Varredura: React.FC<{ readonly dur: number; readonly dir?: 1 | -1 }> = ({ dur, dir = 1 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = interpolate(frame / fps, [0, dur], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const x = dir > 0 ? -400 + k * 2720 : 2320 - k * 2720;
  return (
    <AbsoluteFill style={{ pointerEvents: 'none', mixBlendMode: 'screen' }}>
      <div style={{ position: 'absolute', left: x, top: -200, width: 260, height: 1480, rotate: '14deg', background: 'linear-gradient(90deg, transparent, rgba(0,166,255,.55), rgba(255,255,255,.9), rgba(0,166,255,.55), transparent)', filter: 'blur(18px)' }} />
    </AbsoluteFill>
  );
};
