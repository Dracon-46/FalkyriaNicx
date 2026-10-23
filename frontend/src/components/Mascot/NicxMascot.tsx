import { useEffect, useId, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useMascot, type MascotMood } from '../../lib/mascot';
import { MascotAnimator } from './mascot-animator';
import {
  BODY_OFFSETS,
  computeFrame,
  EYE_RX,
  EYE_RY,
  ORB_OFFSETS,
  ORB_OPACITY,
  phasesAt,
  POSES,
  STILL_INPUT,
  type FrameInput,
} from './mascot-geometry';
import './NicxMascot.css';

export type MascotSize = 'sm' | 'md' | 'lg' | number;

/** Avatar, inline companion and hero sizes, in px. */
export const MASCOT_SIZES = { sm: 28, md: 72, lg: 180 } as const;

export const MASCOT_MOOD_LABELS: Record<MascotMood, string> = {
  idle: 'tranquilo',
  listening: 'ouvindo',
  thinking: 'pensando',
  speaking: 'falando',
  happy: 'feliz',
  error: 'algo deu errado',
};

/** A fixed frame to render instead of animating (stills, exports, tests). */
export type MascotStill = Partial<Omit<FrameInput, 'small'>>;

export interface NicxMascotProps {
  /** 'sm' (28px avatar), 'md' (72px), 'lg' (180px) or any size in px. */
  size?: MascotSize;
  /** Force a mood; by default the mascot follows the shared `useMascot` store. */
  mood?: MascotMood;
  /** Set to false for a static pose (e.g. avatars in long lists). */
  animated?: boolean;
  /** Clicking makes Nicx jiggle and squint happily. */
  interactive?: boolean;
  /** Render one fixed frame; implies `animated={false}`. */
  still?: MascotStill;
  /** Hide from assistive tech when a visible label already names Nicx. */
  decorative?: boolean;
  className?: string;
  style?: CSSProperties;
}

const EYE_INK = '#0b2a31';

/**
 * Nicx, the Falkyria mascot: a translucent cyan slime with two little eyes, no
 * mouth and a blue nucleus floating inside. Expression comes from the eyes,
 * the jelly's squash and stretch and the nucleus.
 */
export function NicxMascot({
  size = 'md',
  mood: moodProp,
  animated = true,
  interactive = false,
  still,
  decorative = false,
  className,
  style,
}: NicxMascotProps) {
  const px = typeof size === 'number' ? size : MASCOT_SIZES[size];
  const storeMood = useMascot((s) => s.mood);
  const mood = moodProp ?? storeMood;
  const small = px < 44;
  const live = animated && !still;

  const uid = `nm${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const ids = {
    body: `${uid}-body`,
    rim: `${uid}-rim`,
    glow: `${uid}-glow`,
    orb: `${uid}-orb`,
    sheen: `${uid}-sheen`,
    shadow: `${uid}-shadow`,
    ground: `${uid}-ground`,
    clip: `${uid}-clip`,
    lidL: `${uid}-lid-l`,
    lidR: `${uid}-lid-r`,
  };

  const stillKey = still ? JSON.stringify(still) : '';
  const staticFrame = useMemo(
    () =>
      computeFrame(POSES[mood], {
        ...STILL_INPUT,
        ...(still?.t !== undefined ? phasesAt(still.t, POSES[mood]) : {}),
        ...still,
        small,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mood, small, stillKey],
  );
  // While animating, React renders the first frame once and the animator
  // owns every attribute after that.
  const [firstFrame] = useState(staticFrame);
  const frame = live ? firstFrame : staticFrame;

  const svgRef = useRef<SVGSVGElement>(null);
  const moodRef = useRef(mood);
  const followsStore = moodProp === undefined;
  const followsStoreRef = useRef(followsStore);
  useEffect(() => {
    moodRef.current = mood;
    followsStoreRef.current = followsStore;
  }, [mood, followsStore]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!live || !svg) return;
    return MascotAnimator.attach(svg, {
      size: px,
      interactive,
      getMood: () => moodRef.current,
      getLevel: () => (followsStoreRef.current ? useMascot.getState().level : 0),
    });
  }, [live, px, interactive]);

  const label = `Nicx (${MASCOT_MOOD_LABELS[mood]})`;
  const outlineWidth = small ? 1.9 : 1.1;
  const lids = [ids.lidL, ids.lidR];

  return (
    <svg
      // Remount when switching between animated and still, so no attribute
      // the animator wrote outlives it.
      key={live ? 'live' : 'still'}
      ref={svgRef}
      // Small avatars crop the headroom kept for hops (overflow stays visible).
      viewBox={small ? '8 16 84 84' : '0 0 100 100'}
      width={px}
      height={px}
      className={['nicx-mascot', interactive ? 'nicx-mascot--interactive' : '', className ?? '']
        .filter(Boolean)
        .join(' ')}
      style={style}
      data-mood={mood}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative ? true : undefined}
      focusable="false"
    >
      <defs>
        <radialGradient id={ids.body} cx="0.42" cy="0.3" r="0.82" fx="0.38" fy="0.22">
          {frame.bodyStops.map((c, i) => (
            <stop key={i} data-part="body-stop" offset={BODY_OFFSETS[i]} stopColor={c} />
          ))}
        </radialGradient>
        <radialGradient id={ids.rim} cx="0.46" cy="0.38" r="0.66">
          <stop offset="0" stopColor="#0aa6bf" stopOpacity="0" />
          <stop offset="0.6" stopColor="#0aa6bf" stopOpacity="0.05" />
          <stop offset="0.88" stopColor="#077f96" stopOpacity="0.32" />
          <stop offset="1" stopColor="#05637a" stopOpacity="0.55" />
        </radialGradient>
        <radialGradient id={ids.glow}>
          <stop offset="0" stopColor="#b4e3ff" stopOpacity="0.85" />
          <stop offset="0.4" stopColor="#4a9cf5" stopOpacity="0.38" />
          <stop offset="1" stopColor="#1c5cab" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={ids.orb}>
          {frame.orbStops.map((c, i) => (
            <stop
              key={i}
              data-part="orb-stop"
              offset={ORB_OFFSETS[i]}
              stopColor={c}
              stopOpacity={ORB_OPACITY[i]}
            />
          ))}
        </radialGradient>
        <radialGradient id={ids.sheen}>
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={ids.shadow}>
          <stop offset="0" stopColor="#0b3b45" stopOpacity="0.3" />
          <stop offset="0.6" stopColor="#0b3b45" stopOpacity="0.14" />
          <stop offset="1" stopColor="#0b3b45" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={ids.ground}>
          <stop offset="0" stopColor="#46e3f5" stopOpacity="0.45" />
          <stop offset="1" stopColor="#46e3f5" stopOpacity="0" />
        </radialGradient>
        <clipPath id={ids.clip}>
          <path data-part="shape" d={frame.body} />
        </clipPath>
        {frame.eyes.map((eye, i) => (
          <clipPath key={i} id={lids[i]} clipPathUnits="userSpaceOnUse">
            <polygon data-part="lid" points={eye.lid} />
          </clipPath>
        ))}
      </defs>

      {/* Ground: soft shadow, plus a cyan reflection in dark themes. */}
      <g className="nm-ground">
        <ellipse className="nm-ground-glow" cx="50" cy="88" rx="38" ry="6.5" fill={`url(#${ids.ground})`} opacity="0" />
        <ellipse
          data-part="shadow"
          className="nm-shadow"
          cx="50"
          cy="88.4"
          rx={frame.shadowRx}
          ry="3.4"
          fill={`url(#${ids.shadow})`}
          opacity={frame.shadowOpacity}
        />
      </g>

      <g data-part="root" transform={frame.root}>
        {/* The outline is written to four paths every frame: cheaper than <use>,
            whose clones Chrome rebuilds whenever the referenced path changes. */}
        <path data-part="shape" d={frame.body} fill={`url(#${ids.body})`} fillOpacity="0.95" />

        {/* Inside the jelly: nucleus, its orbiting sparks and bubbles. */}
        <g clipPath={`url(#${ids.clip})`}>
          <circle
            data-part="glow"
            cx={frame.coreX}
            cy={frame.coreY}
            r={frame.glowR}
            fill={`url(#${ids.glow})`}
            opacity={frame.glowOpacity}
          />
          <ellipse
            data-part="orbit"
            cx="0"
            cy="0"
            rx="10.5"
            ry="4"
            fill="none"
            stroke="#d2ecff"
            strokeWidth="0.45"
            strokeDasharray="1.4 1.8"
            transform={`translate(${frame.coreX} ${frame.coreY}) rotate(-18)`}
            opacity={frame.orbitOpacity}
          />
          <circle
            data-part="orb"
            cx={frame.coreX}
            cy={frame.coreY}
            r={frame.orbR}
            fill={`url(#${ids.orb})`}
            opacity={frame.orbOpacity}
          />
          {frame.swirl.map((d, i) => (
            <circle key={i} data-part="swirl" cx={d.x} cy={d.y} r={d.r} fill="#e6f5ff" opacity={d.o} />
          ))}
          {!small &&
            frame.bubbles.map((d, i) => (
              <circle
                key={i}
                data-part="bubble"
                cx={d.x}
                cy={d.y}
                r={d.r}
                fill="#ffffff"
                fillOpacity="0.28"
                stroke="#ffffff"
                strokeOpacity="0.7"
                strokeWidth="0.35"
                opacity={d.o}
              />
            ))}
          {/* Depth: darker toward the rim, so the nucleus sits inside. */}
          <path data-part="shape" d={frame.body} fill={`url(#${ids.rim})`} />
          <ellipse cx="40" cy="44" rx="21" ry="16" fill={`url(#${ids.sheen})`} />
          {!small && (
            <path
              d="M83.4 69.5Q83.6 81.6 72.5 84.7"
              fill="none"
              stroke="#effeff"
              strokeOpacity="0.6"
              strokeWidth="1.3"
              strokeLinecap="round"
            />
          )}
        </g>

        <path
          data-part="shape"
          d={frame.body}
          className="nm-outline"
          fill="none"
          stroke="#0b8aa3"
          strokeOpacity="0.55"
          strokeWidth={outlineWidth}
        />

        {/* Glossy highlight. */}
        <path d="M23.4 64Q21.2 40 39.5 32.5Q27.8 41.5 23.4 64Z" fill="#ffffff" opacity="0.78" />
        <circle cx="22.4" cy="68.6" r="1.3" fill="#ffffff" opacity="0.8" />

        {[31.2, 68.8].map((x) => (
          <ellipse
            key={x}
            data-part="blush"
            cx={x}
            cy="61.5"
            rx="3.7"
            ry="1.9"
            fill="#ff8fab"
            opacity={frame.blush}
          />
        ))}

        {frame.eyes.map((eye, i) => (
          <g key={i} data-part="eye" transform={eye.transform}>
            <g data-part="eye-open" transform={eye.openTransform} opacity={eye.openOpacity}>
              <g clipPath={`url(#${lids[i]})`}>
                <ellipse rx={EYE_RX} ry={EYE_RY} fill={EYE_INK} />
                <circle cx="1.35" cy="-2.1" r="1.55" fill="#ffffff" />
                <circle cx="-1.3" cy="2.3" r="0.7" fill="#ffffff" opacity="0.7" />
              </g>
            </g>
            <path
              data-part="eye-happy"
              d="M-4.1 1.6Q0 -4.9 4.1 1.6"
              fill="none"
              stroke={EYE_INK}
              strokeWidth="2.1"
              strokeLinecap="round"
              opacity={eye.happy}
              transform={eye.happyTransform}
            />
          </g>
        ))}
      </g>
    </svg>
  );
}
