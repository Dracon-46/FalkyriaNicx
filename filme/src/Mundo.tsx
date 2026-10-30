import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
// @ts-expect-error motor em JS puro
import { criarMotor } from './motor/motor.js';
import linha from './linha.json';

type Plano = (typeof linha.planos)[number] & { opts?: Record<string, unknown>; congela?: boolean };
const PLANOS = linha.planos as Plano[];

const planoEm = (t: number) => PLANOS.find((p) => t >= p.ini && t < p.fim);
// amostra do mundo num instante: qual set, tempo local e início do plano (o motion blur não cruza cortes)
const amostra = (t: number) => {
  const p = planoEm(t) ?? PLANOS[PLANOS.length - 1];
  return { set: p.set, u: p.congela ? p.u0 : p.u0 + (t - p.ini), opts: p.opts ?? {}, tAbs: t, start: p.ini };
};
const subquadros = (t: number) => (linha.rapidos.some(([a, b]) => t >= a && t < b) ? 12 : 6);

const URLS = Object.fromEntries(
  ['contratacoes', 'economia', 'conformidade', 'home', 'mapa_estados'].map((n) => [n, staticFile(`lumen/${n}.png`)]),
);

export const Mundo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const ref = useRef<HTMLCanvasElement>(null);
  const [motor, setMotor] = useState<{ render: (t: number, s: typeof amostra, sub: number, fps: number) => void } | null>(null);
  const [handle] = useState(() => delayRender('Carregando o motor 3D', { timeoutInMilliseconds: 180000 }));

  useEffect(() => {
    let vivo = true;
    criarMotor(ref.current, URLS).then((m: typeof motor) => {
      if (!vivo) return;
      setMotor(m);
      continueRender(handle);
    });
    return () => {
      vivo = false;
    };
  }, [handle]);

  const t = frame / fps;
  const ativo = Boolean(planoEm(t));
  useLayoutEffect(() => {
    if (motor && ativo) motor.render(t, amostra, subquadros(t), fps);
  }, [motor, t, ativo, fps]);

  return <canvas ref={ref} width={width} height={height} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: ativo ? 1 : 0 }} />;
};
