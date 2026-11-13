import React, {useId} from 'react';
import raw from '../profiles.json';
import {C, DISPLAY, mix} from '../theme';

type Poly = number[][];
type Frame = {
  si: Poly[];
  mask: Poly[];
  ox: Poly[];
  micro: Poly[];
  passiv: number[][];
  walls?: Poly[];
  stats: {depth: number; depths?: number[]; undercut?: number; notch?: number; cycle?: number; cycles?: number};
};
export type Scene = {
  label: string;
  viewBox: number[];
  fps: number;
  openings: number[][];
  oxide_top: number;
  frames: Frame[];
};

export const SCENES = raw as unknown as Record<string, Scene>;

export const getFrame = (id: string, progress: number): Frame => {
  const s = SCENES[id];
  const idx = Math.min(s.frames.length - 1, Math.max(0, Math.round(progress * (s.frames.length - 1))));
  return s.frames[idx];
};

export const pathOf = (poly: Poly) =>
  poly.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ') + ' Z';

const Label: React.FC<{x: number; y: number; text: string; color: string; size?: number}> = ({
  x,
  y,
  text,
  color,
  size = 8.5,
}) => (
  <text
    x={x}
    y={y}
    fill={color}
    fontFamily={DISPLAY}
    fontWeight={800}
    fontSize={size}
    letterSpacing={1.1}
    opacity={0.9}
  >
    {text}
  </text>
);

export const Profile: React.FC<{
  id: string;
  progress: number;
  zoom?: number;
  translate?: [number, number];
  accent?: string;
  showPassiv?: boolean;
  showLabels?: boolean;
  opacity?: number;
  className?: string;
  style?: React.CSSProperties;
  viewBox?: number[];
  children?: React.ReactNode;
}> = ({
  id,
  progress,
  zoom = 1,
  translate = [0, 0],
  accent = C.cyan,
  showPassiv = true,
  showLabels = true,
  opacity = 1,
  style,
  viewBox,
  children,
}) => {
  const s = SCENES[id];
  const fr = getFrame(id, progress);
  const uid = useId().replace(/[:]/g, '');
  const vbArr = viewBox ?? s.viewBox;
  const vb = vbArr.join(' ');
  const [vx, vy, vw, vh] = vbArr;
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        borderRadius: 26,
        background: 'linear-gradient(160deg, rgba(10,22,32,0.92), rgba(5,9,14,0.97))',
        border: '1px solid rgba(95,243,255,0.16)',
        boxShadow: 'inset 0 0 80px rgba(0,0,0,0.7)',
        opacity,
        ...style,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `scale(${zoom}) translate(${translate[0]}%, ${translate[1]}%)`,
          transformOrigin: 'center',
        }}
      >
        <svg viewBox={vb} style={{width: '100%', height: '100%', display: 'block'}}>
          <defs>
            <linearGradient id={`si${uid}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0F3B47" />
              <stop offset="55%" stopColor="#0B2730" />
              <stop offset="100%" stopColor="#071820" />
            </linearGradient>
            <linearGradient id={`mask${uid}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3A2708" />
              <stop offset="100%" stopColor="#1B1205" />
            </linearGradient>
            <linearGradient id={`ox${uid}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2A1850" />
              <stop offset="100%" stopColor="#150B2A" />
            </linearGradient>
            <filter id={`glow${uid}`} x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="2.2" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <pattern id={`grid${uid}`} width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M20,0 L0,0 L0,20" fill="none" stroke="#5FF3FF" strokeWidth="0.25" opacity="0.18" />
            </pattern>
          </defs>

          <rect x={vx} y={vy} width={vw} height={vh} fill="#050A10" />
          <rect x={vx} y={vy} width={vw} height={vh} fill={`url(#grid${uid})`} />

          <g filter={`url(#glow${uid})`}>
            {fr.ox.map((p, i) => (
              <path key={`ox${i}`} d={pathOf(p)} fill={`url(#ox${uid})`} stroke={C.violet} strokeWidth={0.9} />
            ))}
            {fr.si.map((p, i) => (
              <path key={`si${i}`} d={pathOf(p)} fill={`url(#si${uid})`} stroke={C.teal} strokeWidth={1.1} />
            ))}
            {fr.micro.map((p, i) => (
              <path key={`m${i}`} d={pathOf(p)} fill="#3A2608" stroke={C.amber} strokeWidth={0.9} />
            ))}
            {fr.mask.map((p, i) => (
              <path key={`mask${i}`} d={pathOf(p)} fill={`url(#mask${uid})`} stroke={C.amber} strokeWidth={0.9} />
            ))}
            {showPassiv &&
              fr.passiv.map((r, i) => (
                <rect
                  key={`p${i}`}
                  x={r[0]}
                  y={r[1]}
                  width={r[2] - r[0]}
                  height={r[3] - r[1]}
                  fill={C.pink}
                  opacity={0.78}
                />
              ))}
            {fr.walls?.map((w, i) => (
              <polyline
                key={`w${i}`}
                points={w.map((p) => `${p[0]},${p[1]}`).join(' ')}
                fill="none"
                stroke={C.pink}
                strokeWidth={1.4}
                opacity={0.9}
              />
            ))}
          </g>

          {showLabels && (
            <>
              <Label x={vx + 8} y={vy + 16} text="MASK" color={C.amber} />
              <Label x={vx + 8} y={vy + 52} text="Si" color={C.teal} />
              <Label x={vx + 8} y={vy + vh - 10} text="SiO₂ STOP" color={C.violet} />
              <g opacity={0.75}>
                <line
                  x1={vx + vw - 118}
                  y1={vy + vh - 8}
                  x2={vx + vw - 8}
                  y2={vy + vh - 8}
                  stroke={accent}
                  strokeWidth={1.6}
                />
                <line x1={vx + vw - 118} y1={vy + vh - 13} x2={vx + vw - 118} y2={vy + vh - 3} stroke={accent} strokeWidth={1.6} />
                <line x1={vx + vw - 8} y1={vy + vh - 13} x2={vx + vw - 8} y2={vy + vh - 3} stroke={accent} strokeWidth={1.6} />
                <text
                  x={vx + vw - 63}
                  y={vy + vh - 15}
                  fill={accent}
                  fontFamily={DISPLAY}
                  fontWeight={800}
                  fontSize={8}
                  letterSpacing={1}
                  textAnchor="middle"
                >
                  100 nm
                </text>
              </g>
            </>
          )}
        </svg>
      </div>
      {children}

      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'repeating-linear-gradient(to bottom, rgba(255,255,255,0.035) 0px, rgba(255,255,255,0.035) 1px, transparent 1px, transparent 4px)',
          pointerEvents: 'none',
          mixBlendMode: 'screen',
        }}
      />
      {[
        {left: 14, top: 14, borderLeft: `2px solid ${accent}`, borderTop: `2px solid ${accent}`},
        {right: 14, top: 14, borderRight: `2px solid ${accent}`, borderTop: `2px solid ${accent}`},
        {left: 14, bottom: 14, borderLeft: `2px solid ${accent}`, borderBottom: `2px solid ${accent}`},
        {right: 14, bottom: 14, borderRight: `2px solid ${accent}`, borderBottom: `2px solid ${accent}`},
      ].map((st, i) => (
        <div key={i} style={{position: 'absolute', width: 16, height: 16, opacity: 0.7, ...st}} />
      ))}
    </div>
  );
};

export const depthNm = (cells: number) => Math.round(mix(0, 420, Math.min(1, cells / 130)));
