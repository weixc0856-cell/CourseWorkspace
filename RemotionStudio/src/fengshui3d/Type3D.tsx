import React from 'react';
import {useCurrentFrame} from 'remotion';
import {DISPLAY, SANS, clamp01, easeOut} from '../fengshui/theme';

export const T3 = {
  paper: '#F1EAD9',
  body: '#D7D0BF',
  muted: '#8FA39E',
  faint: '#5D7370',
  gold: '#E0A45C',
  goldDeep: '#C07F3A',
  cyan: '#8FD8D2',
  cinnabar: '#B4482F',
  ink: '#0A1416',
};

export const useT = () => useCurrentFrame() / 30;

export const Big3: React.FC<{
  lines: string[];
  start: number;
  size?: number;
  top?: number;
  left?: number;
  right?: number;
  accent?: string;
  stagger?: number;
  weight?: number;
}> = ({lines, start, size = 96, top = 250, left = 84, right = 84, accent, stagger = 0.06, weight = 900}) => {
  const t = useT();
  const norm = (s: string) => s.toUpperCase().replace(/[^A-Z0-9]/g, '');
  let idx = 0;
  return (
    <div style={{position: 'absolute', top, left, right}}>
      {lines.map((line, li) => (
        <div key={li} style={{overflow: 'hidden', lineHeight: 0.94, whiteSpace: 'nowrap'}}>
          {line.split(' ').map((word, wi) => {
            const isAccent = accent ? norm(word) === norm(accent) : false;
            const d = start + idx * stagger + (isAccent ? 0.15 : 0);
            idx += 1;
            const p = easeOut(clamp01((t - d) / 0.5));
            return (
              <span
                key={wi}
                style={{
                  display: 'inline-block',
                  overflow: 'hidden',
                  verticalAlign: 'top',
                  paddingBottom: '0.07em',
                  marginRight: size * 0.16,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    fontFamily: DISPLAY,
                    fontWeight: weight,
                    fontSize: size,
                    letterSpacing: isAccent ? `${(0.06 - 0.09 * p).toFixed(3)}em` : '-0.028em',
                    textTransform: 'uppercase',
                    color: isAccent ? T3.gold : T3.paper,
                    transform: `translateY(${(1 - p) * 108}%)`,
                    opacity: p > 0 ? 1 : 0,
                    textShadow: isAccent ? `0 0 32px ${T3.gold}44` : 'none',
                  }}
                >
                  {word}
                </span>
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export const Small3: React.FC<{
  text: string;
  start: number;
  top: number;
  color?: string;
  size?: number;
  left?: number;
  right?: number;
}> = ({text, start, top, color = T3.muted, size = 22, left = 84, right = 84}) => {
  const t = useT();
  const p = easeOut(clamp01((t - start) / 0.7));
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left,
        right,
        fontFamily: DISPLAY,
        fontSize: size,
        letterSpacing: '0.2em',
        color,
        opacity: p,
        transform: `translateY(${(1 - p) * 8}px)`,
        lineHeight: 1.7,
        whiteSpace: 'pre-line',
      }}
    >
      {text}
    </div>
  );
};

export const Caption3: React.FC<{zh: string; start: number; end?: number; top?: number}> = ({
  zh,
  start,
  end,
  top = 1720,
}) => {
  const t = useT();
  const bar = easeOut(clamp01((t - start) / 0.15));
  const wipe = easeOut(clamp01((t - start - 0.12) / 0.45));
  const out = end ? clamp01((t - end) / 0.3) : 0;
  return (
    <div style={{position: 'absolute', left: 84, right: 84, top, opacity: 1 - out}}>
      <div style={{display: 'flex', alignItems: 'flex-start', gap: 18}}>
        <div style={{width: 3, height: 30 * bar, background: T3.gold, marginTop: 8, opacity: 0.9}} />
        <div
          style={{
            fontFamily: SANS,
            fontSize: 40,
            lineHeight: 1.45,
            color: T3.paper,
            letterSpacing: '0.02em',
            clipPath: `inset(0 ${(1 - wipe) * 100}% 0 0)`,
          }}
        >
          {zh}
        </div>
      </div>
    </div>
  );
};

export const Quote3: React.FC<{columns: string[]; start: number; top?: number; size?: number}> = ({
  columns,
  start,
  top = 300,
  size = 92,
}) => {
  const t = useT();
  return (
    <div style={{position: 'absolute', top, right: 110, display: 'flex', flexDirection: 'row-reverse', gap: 26}}>
      {columns.map((col, i) => {
        const p = easeOut(clamp01((t - start - i * 0.5) / 1.1));
        return (
          <div
            key={i}
            style={{
              writingMode: 'vertical-rl',
              fontFamily: '"STKaiti", "KaiTi", serif',
              fontSize: size,
              lineHeight: 1.16,
              letterSpacing: '0.04em',
              color: T3.paper,
              opacity: p,
              clipPath: `inset(0 0 ${(1 - p) * 100}% 0)`,
              textShadow: '0 0 26px rgba(224,164,92,0.18)',
            }}
          >
            {col}
          </div>
        );
      })}
    </div>
  );
};

export const Seal3: React.FC<{chars: string; start: number; top: number; left: number; size?: number}> = ({
  chars,
  start,
  top,
  left,
  size = 140,
}) => {
  const t = useT();
  const p = clamp01((t - start) / 0.3);
  if (p <= 0) return null;
  const s = 1.35 - 0.35 * easeOut(p);
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left,
        width: size,
        height: size,
        background: T3.cinnabar,
        transform: `rotate(-3deg) scale(${s})`,
        opacity: Math.min(1, p * 1.6),
        boxShadow: `0 0 42px rgba(180,72,47,0.35)`,
        outline: `3px solid ${T3.cinnabar}`,
        outlineOffset: 4,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {chars.split('').map((c, i) => (
        <span key={i} style={{fontFamily: '"STSong", "SimSun", serif', fontSize: size * 0.44, color: T3.paper, lineHeight: 1.04}}>
          {c}
        </span>
      ))}
    </div>
  );
};
