import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, DISPLAY, SANS, caps} from '../theme';

export const Kicker: React.FC<{
  text: string;
  color?: string;
  delay?: number;
  align?: 'left' | 'center';
  size?: number;
}> = ({text, color = C.muted, delay = 0, align = 'left', size = 22}) => {
  const frame = useCurrentFrame();
  const p = spring({frame: frame - delay, fps: 30, config: {damping: 22, stiffness: 200}});
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: align === 'center' ? 'center' : 'flex-start',
        gap: 16,
        opacity: p,
        transform: `translateY(${(1 - p) * 14}px)`,
      }}
    >
      <div style={{width: 46 * p, height: 2, background: color, boxShadow: `0 0 12px ${color}`}} />
      <div
        style={{
          fontFamily: DISPLAY,
          fontWeight: 800,
          fontSize: size,
          letterSpacing: '0.28em',
          textTransform: 'uppercase',
          color,
        }}
      >
        {text}
      </div>
    </div>
  );
};

export const Giant: React.FC<{
  lines: string[];
  size?: number;
  delay?: number;
  color?: string;
  accent?: string;
  accentColor?: string;
  align?: 'left' | 'center';
  weight?: number;
  lineHeight?: number;
  letterSpacing?: string;
}> = ({
  lines,
  size = 128,
  delay = 0,
  color = C.ink,
  accent,
  accentColor = C.cyan,
  align = 'left',
  weight = 900,
  lineHeight = 0.86,
  letterSpacing = '-0.035em',
}) => {
  const frame = useCurrentFrame();
  let wordIndex = 0;
  return (
    <div style={{textAlign: align, width: '100%'}}>
      {lines.map((line, li) => (
        <div key={li} style={{overflow: 'hidden', lineHeight}}>
          {line.split(' ').map((word, wi) => {
            const d = delay + (li * 3 + wi) * 2.2;
            const p = spring({frame: frame - d, fps: 30, config: {damping: 20, stiffness: 260, mass: 0.55}});
            const isAccent = accent && word.toUpperCase().replace(/[^A-Z0-9:]/g, '') === accent.toUpperCase().replace(/[^A-Z0-9:]/g, '');
            wordIndex += 1;
            return (
              <span
                key={wi}
                style={{
                  display: 'inline-block',
                  fontFamily: DISPLAY,
                  fontWeight: weight,
                  fontSize: size,
                  letterSpacing,
                  textTransform: 'uppercase',
                  color: isAccent ? accentColor : color,
                  transform: `translateY(${(1 - p) * 112}%)`,
                  opacity: p,
                  filter: `blur(${(1 - p) * 6}px)`,
                  textShadow: isAccent ? `0 0 46px ${accentColor}55` : 'none',
                  marginRight: size * 0.16,
                }}
              >
                {word}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export const Caption: React.FC<{
  en: string;
  zh: string;
  accent?: string;
  delay?: number;
}> = ({en, zh, accent = C.cyan, delay = 8}) => {
  const frame = useCurrentFrame();
  const p = spring({frame: frame - delay, fps: 30, config: {damping: 24, stiffness: 160}});
  return (
    <>
      <AbsoluteFill
        style={{
          background: `linear-gradient(to top, rgba(5,7,12,0.96) 0%, rgba(5,7,12,0.82) 44%, rgba(5,7,12,0) 100%)`,
          top: 'auto',
          height: 460,
          bottom: 0,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: caps.left,
          right: caps.right,
          top: caps.top,
          opacity: p,
          transform: `translateY(${(1 - p) * 18}px)`,
        }}
      >
        <div style={{display: 'flex', gap: 18}}>
          <div style={{width: 3, background: accent, boxShadow: `0 0 14px ${accent}`, borderRadius: 2}} />
          <div>
            <div
              style={{
                fontFamily: DISPLAY,
                fontWeight: 300,
                fontSize: 24,
                lineHeight: 1.35,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: C.muted,
                marginBottom: 14,
              }}
            >
              {en}
            </div>
            <div
              style={{
                fontFamily: SANS,
                fontWeight: 400,
                fontSize: 38,
                lineHeight: 1.55,
                color: C.body,
                letterSpacing: '0.01em',
              }}
            >
              {zh}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export const ChapterTag: React.FC<{chapter: string; kicker: string; color?: string}> = ({
  chapter,
  kicker,
  color = C.cyan,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, 14], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        position: 'absolute',
        left: caps.left,
        top: 96,
        opacity: p,
        transform: `translateY(${(1 - p) * 12}px)`,
      }}
    >
      <div
        style={{
          fontFamily: DISPLAY,
          fontWeight: 800,
          fontSize: 20,
          letterSpacing: '0.3em',
          color: C.muted,
          textTransform: 'uppercase',
        }}
      >
        {chapter}
      </div>
    </div>
  );
};

export const TopHud: React.FC<{t: number}> = ({t}) => {
  const blink = Math.sin(t * Math.PI * 2 * 1.2) > 0 ? 1 : 0.2;
  return (
    <div
      style={{
        position: 'absolute',
        right: caps.right,
        top: 100,
        textAlign: 'right',
        fontFamily: DISPLAY,
        fontWeight: 800,
        fontSize: 17,
        letterSpacing: '0.24em',
        color: C.muted,
        textTransform: 'uppercase',
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10}}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: 4,
            background: C.cyan,
            opacity: blink,
            boxShadow: `0 0 10px ${C.cyan}`,
          }}
        />
        SIMULATION
      </div>
      <div style={{marginTop: 7, color: C.faint}}>QUALITATIVE ONLY</div>
    </div>
  );
};

export const Note: React.FC<{text: string; color?: string}> = ({text, color = C.faint}) => (
  <div
    style={{
      fontFamily: DISPLAY,
      fontWeight: 800,
      fontSize: 16,
      letterSpacing: '0.24em',
      textTransform: 'uppercase',
      color,
    }}
  >
    {text}
  </div>
);
