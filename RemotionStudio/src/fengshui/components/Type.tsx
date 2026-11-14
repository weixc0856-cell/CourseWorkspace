import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {DISPLAY, FPS, P, SANS, clamp01, easeOut} from '../theme';

export const useT = () => useCurrentFrame() / FPS;

const reveal = (t: number, start: number, dur = 0.55) => {
  const p = clamp01((t - start) / dur);
  return {p: easeOut(p)};
};

export const Big: React.FC<{
  lines: string[];
  start: number;
  size?: number;
  color?: string;
  accent?: string;
  accentColor?: string;
  weight?: number;
  lineHeight?: number;
  top?: number;
  left?: number;
  right?: number;
  align?: 'left' | 'center';
  stagger?: number;
}> = ({
  lines,
  start,
  size = 96,
  color = P.ink,
  accent,
  accentColor = P.cinnabar,
  weight = 900,
  lineHeight = 0.94,
  top = 250,
  left = 84,
  right = 84,
  align = 'left',
  stagger = 0.06,
}) => {
  const t = useT();
  const norm = (s: string) => s.toUpperCase().replace(/[^A-Z0-9]/g, '');
  let idx = 0;
  return (
    <div style={{position: 'absolute', top, left, right, textAlign: align}}>
      {lines.map((line, li) => (
        <div key={li} style={{overflow: 'hidden', lineHeight, whiteSpace: 'nowrap'}}>
          {line.split(' ').map((word, wi) => {
            const isAccent = accent ? norm(word) === norm(accent) : false;
            const d = start + idx * stagger + (isAccent ? 0.15 : 0);
            idx += 1;
            const p = easeOut(clamp01((t - d) / 0.5));
            const spacing = isAccent ? `${(0.07 - 0.1 * p).toFixed(3)}em` : '-0.028em';
            return (
              <span
                key={wi}
                style={{
                  display: 'inline-block',
                  overflow: 'hidden',
                  verticalAlign: 'top',
                  paddingBottom: '0.06em',
                  marginRight: size * 0.16,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    fontFamily: DISPLAY,
                    fontWeight: weight,
                    fontSize: size,
                    letterSpacing: spacing,
                    textTransform: 'uppercase',
                    color: isAccent ? accentColor : color,
                    transform: `translateY(${(1 - p) * 108}%)`,
                    opacity: p > 0 ? 1 : 0,
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

export const Small: React.FC<{
  text: string;
  start: number;
  color?: string;
  size?: number;
  top?: number;
  left?: number;
  right?: number;
  align?: 'left' | 'center';
  tracking?: string;
}> = ({text, start, color = P.inkSoft, size = 23, top, left = 84, right = 84, align = 'left', tracking = '0.2em'}) => {
  const t = useT();
  const p = clamp01((t - start) / 0.7);
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left,
        right,
        textAlign: align,
        fontFamily: DISPLAY,
        fontWeight: 400,
        fontSize: size,
        letterSpacing: tracking,
        textTransform: 'uppercase',
        color,
        opacity: easeOut(p),
        transform: `translateY(${(1 - easeOut(p)) * 8}px)`,
      }}
    >
      {text}
    </div>
  );
};

export const Rule: React.FC<{start: number; top: number; left?: number; width?: number; color?: string}> = ({
  start,
  top,
  left = 84,
  width = 148,
  color = P.ink,
}) => {
  const t = useT();
  const p = easeOut(clamp01((t - start) / 0.7));
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left,
        width: width * p,
        height: 2,
        background: color,
        opacity: 0.85,
      }}
    />
  );
};

export const ZhCaption: React.FC<{
  zh: string;
  start: number;
  end?: number;
  top?: number;
  accent?: string;
}> = ({zh, start, end, top = 1704, accent = P.ink}) => {
  const t = useT();
  const bar = easeOut(clamp01((t - start) / 0.15));
  const wipe = easeOut(clamp01((t - start - 0.12) / 0.45));
  const out = end ? clamp01((t - end) / 0.3) : 0;
  return (
    <div
      style={{
        position: 'absolute',
        left: 84,
        right: 84,
        top,
        opacity: 1 - out,
      }}
    >
      <div style={{display: 'flex', alignItems: 'flex-start', gap: 18}}>
        <div style={{width: 3, height: 30 * bar, background: P.cinnabar, marginTop: 8, opacity: 0.9}} />
        <div
          style={{
            fontFamily: SANS,
            fontWeight: 400,
            fontSize: 40,
            lineHeight: 1.45,
            color: accent,
            letterSpacing: '0.02em',
            clipPath: `inset(0 ${(1 - wipe) * 100}% 0 0)`,
            transform: `translateY(${(1 - wipe) * 4}px)`,
          }}
        >
          {zh}
        </div>
      </div>
    </div>
  );
};

// Vertical classical quote, right to left, in a Kai face.
export const Quote: React.FC<{
  columns: string[];
  start: number;
  top?: number;
  right?: number;
  size?: number;
  color?: string;
}> = ({columns, start, top = 300, right = 120, size = 96, color = P.ink}) => {
  const t = useT();
  return (
    <div
      style={{
        position: 'absolute',
        top,
        right,
        display: 'flex',
        flexDirection: 'row-reverse',
        gap: 26,
      }}
    >
      {columns.map((col, i) => {
        const p = easeOut(clamp01((t - start - i * 0.5) / 1.1));
        return (
          <div
            key={i}
            style={{
              writingMode: 'vertical-rl',
              fontFamily: '"STKaiti", "KaiTi", "Adobe Kaiti Std", serif',
              fontSize: size,
              lineHeight: 1.16,
              letterSpacing: '0.04em',
              color,
              opacity: p,
              clipPath: `inset(0 0 ${(1 - p) * 100}% 0)`,
            }}
          >
            {col}
          </div>
        );
      })}
    </div>
  );
};

export const Seal: React.FC<{
  chars: string;
  start: number;
  size?: number;
  top: number;
  left: number;
  rotate?: number;
  color?: string;
}> = ({chars, start, size = 156, top, left, rotate = -3, color = P.cinnabar}) => {
  const t = useT();
  const p = clamp01((t - start) / 0.32);
  if (p <= 0) return null;
  const s = interpolate(p, [0, 1], [1.35, 1]);
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left,
        width: size,
        height: size,
        background: color,
        transform: `rotate(${rotate}deg) scale(${s})`,
        opacity: Math.min(1, p * 1.6),
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: 'inset 0 0 0 6px rgba(245,240,230,0.0), inset 0 0 0 5px ' + color,
        outline: `3px solid ${color}`,
        outlineOffset: 4,
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: '"STSong", "SimSun", serif',
          fontSize: size * 0.44,
          color: P.paper,
          lineHeight: 1.02,
        }}
      >
        {chars.split('').map((c, i) => (
          <span key={i}>{c}</span>
        ))}
      </div>
    </div>
  );
};

export const Meta: React.FC<{text: string; start: number; top: number; right?: number; left?: number; color?: string}> = ({
  text,
  start,
  top,
  right = 84,
  left,
  color = P.inkFaint,
}) => {
  const t = useT();
  const p = easeOut(clamp01((t - start) / 0.8));
  return (
    <div
      style={{
        position: 'absolute',
        top,
        right,
        left,
        textAlign: left === undefined ? 'right' : 'left',
        fontFamily: DISPLAY,
        fontWeight: 400,
        fontSize: 19,
        letterSpacing: '0.14em',
        color,
        opacity: p,
        lineHeight: 1.6,
        whiteSpace: 'pre-line',
      }}
    >
      {text}
    </div>
  );
};
