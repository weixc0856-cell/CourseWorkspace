import React, {useId} from 'react';
import {C, mulberry32} from '../theme';
import {SCENES, getFrame} from './Profile';

const MASK_BOT = 40;

export const Ions: React.FC<{
  sceneId: string;
  t: number;
  progress: number;
  intensity?: number;
  color?: string;
  mode?: 'ion' | 'chem' | 'polymer';
  count?: number;
  seed?: number;
  viewBox?: number[];
}> = ({sceneId, t, progress, intensity = 1, color = C.cyan, mode = 'ion', count = 80, seed = 11, viewBox}) => {
  const uid = useId().replace(/[:]/g, '');
  const s = SCENES[sceneId];
  const fr = getFrame(sceneId, progress);
  const depth = Math.max(20, fr.stats.depth);
  const y0 = s.viewBox[1] + 4;
  const y1 = MASK_BOT + depth * 0.92;
  const openings = s.openings;
  const rand = mulberry32(seed);
  const parts = new Array(count).fill(0).map((_, i) => {
    const r1 = rand();
    const r2 = rand();
    const r3 = rand();
    const r4 = rand();
    const op = openings[Math.floor(r4 * openings.length) % openings.length];
    const x = op[0] + 2 + r1 * Math.max(1, op[1] - op[0] - 4);
    const speed = mode === 'polymer' ? 0.25 + r2 * 0.25 : 0.75 + r2 * 0.8;
    const phase = ((t * speed + r3) % 1 + 1) % 1;
    const y = y0 + phase * (y1 - y0);
    const len = mode === 'chem' ? 1.5 + r2 * 2.5 : 4 + r3 * 13;
    const wobble = Math.sin(t * 2.4 + i * 1.7) * (mode === 'chem' ? 2.2 : 0.9);
    return {x: x + wobble, y, len, r1, r2, phase};
  });
  const env = (p: number) => Math.sin(Math.PI * Math.min(1, Math.max(0, p)));
  return (
    <svg
      viewBox={(viewBox ?? s.viewBox).join(' ')}
      style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}
    >
      <defs>
        <filter id={`ig${uid}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="0.9" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id={`sheath${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0" />
          <stop offset="55%" stopColor={color} stopOpacity="0.55" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect
        x={openings[0][0]}
        y={26}
        width={openings[openings.length - 1][1] - openings[0][0]}
        height={12}
        fill={`url(#sheath${uid})`}
        opacity={0.55 * intensity}
      />
      <g filter={`url(#ig${uid})`}>
        {parts.map((p, i) => {
          const a = env(p.phase) * intensity;
          if (mode === 'chem') {
            return <circle key={i} cx={p.x} cy={p.y} r={1.1 + p.r2 * 1.4} fill={color} opacity={a * 0.75} />;
          }
          return (
            <g key={i} opacity={a}>
              <line
                x1={p.x}
                y1={p.y - p.len}
                x2={p.x}
                y2={p.y}
                stroke={color}
                strokeWidth={mode === 'polymer' ? 1.15 : 0.85}
                strokeLinecap="round"
              />
              <circle cx={p.x} cy={p.y} r={mode === 'polymer' ? 1.15 : 0.85} fill={color} />
            </g>
          );
        })}
      </g>
    </svg>
  );
};

export const SheathLabel: React.FC<{sceneId: string; text?: string; color?: string}> = ({
  sceneId,
  text = 'PLASMA SHEATH',
  color = C.cyan,
}) => {
  const s = SCENES[sceneId];
  return (
    <svg
      viewBox={s.viewBox.join(' ')}
      style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}
    >
      <text
        x={s.openings[0][0] + 2}
        y={24}
        fill={color}
        fontFamily="JostVibe"
        fontWeight={800}
        fontSize={6.5}
        letterSpacing={1.1}
        opacity={0.8}
      >
        {text}
      </text>
    </svg>
  );
};
