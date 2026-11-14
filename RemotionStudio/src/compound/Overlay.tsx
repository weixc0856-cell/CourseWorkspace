import React from 'react';
import {interpolate, spring} from 'remotion';
import {
  C,
  FPS,
  REMOVE,
  REVEAL,
  RESTORE,
  STAGE_TIMES,
  beatPulse,
  easeOut,
  smooth,
  stageAt,
} from './timeline';

export const DISPLAY = 'JostVibe';
export const SANS = 'NotoSCVibe';

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export const Headline: React.FC<{
  lines: string[];
  start: number;
  end: number;
  t: number;
  size?: number;
  color?: string;
  accent?: string;
  accentColor?: string;
  top?: number;
  align?: 'left' | 'center';
}> = ({
  lines,
  start,
  end,
  t,
  size = 92,
  color = C.ink,
  accent,
  accentColor = C.cyan,
  top = 140,
  align = 'center',
}) => {
  const local = t - start;
  if (local < -0.1 || t > end + 0.1) return null;
  const op = interpolate(t, [start, start + 0.2, end - 0.28, end], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        position: 'absolute',
        left: 80,
        right: 80,
        top,
        textAlign: align,
        opacity: op,
      }}
    >
      {lines.map((line, li) => {
        const p = spring({
          frame: Math.max(0, local * FPS - li * 2.4),
          fps: FPS,
          config: {damping: 20, stiffness: 260, mass: 0.6},
        });
        return (
          <div key={li} style={{overflow: 'hidden', lineHeight: 0.9}}>
            <div
              style={{
                display: 'inline-block',
                transform: `translateY(${(1 - p) * 105}%) scale(${0.96 + p * 0.04})`,
                filter: `blur(${(1 - p) * 5}px)`,
              }}
            >
              {line.split(' ').map((word, wi) => {
                const isAccent =
                  accent &&
                  word.toUpperCase().replace(/[^A-Z0-9:]/g, '') ===
                    accent.toUpperCase().replace(/[^A-Z0-9:]/g, '');
                return (
                  <span
                    key={wi}
                    style={{
                      display: 'inline-block',
                      fontFamily: DISPLAY,
                      fontWeight: 900,
                      fontSize: size,
                      lineHeight: 0.92,
                      letterSpacing: '-0.035em',
                      textTransform: 'uppercase',
                      color: isAccent ? accentColor : color,
                      textShadow: isAccent ? `0 0 38px ${accentColor}66` : '0 0 28px rgba(0,0,0,0.55)',
                      marginRight: size * 0.16,
                    }}
                  >
                    {word}
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const Caption: React.FC<{
  zh: string;
  start: number;
  end: number;
  t: number;
  color?: string;
}> = ({zh, start, end, t, color = C.cyan}) => {
  if (t < start - 0.1 || t > end + 0.1) return null;
  const op = interpolate(t, [start, start + 0.25, end - 0.25, end], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 420,
          background:
            'linear-gradient(to top, rgba(5,7,12,0.92) 0%, rgba(5,7,12,0.55) 45%, rgba(5,7,12,0) 100%)',
          opacity: op,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 120,
          right: 120,
          bottom: 150,
          display: 'flex',
          gap: 20,
          justifyContent: 'center',
          alignItems: 'stretch',
          opacity: op,
          transform: `translateY(${(1 - op) * 12}px)`,
        }}
      >
        <div style={{width: 3, background: color, boxShadow: `0 0 16px ${color}`, borderRadius: 2}} />
        <div
          style={{
            fontFamily: SANS,
            fontWeight: 400,
            fontSize: 36,
            lineHeight: 1.55,
            color: C.body,
            textAlign: 'left',
          }}
        >
          {zh}
        </div>
      </div>
    </>
  );
};

export const Counter: React.FC<{t: number}> = ({t}) => {
  const {k} = stageAt(t);
  const count = 1 << k;
  const reveal = t >= REVEAL && t < END_COUNTER;
  const removed = t >= REMOVE && t < RESTORE;
  const op = interpolate(t, [1.5, 2.5, 148, 150], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        position: 'absolute',
        right: 80,
        bottom: 430,
        textAlign: 'right',
        opacity: op,
        fontFamily: DISPLAY,
        textTransform: 'uppercase',
      }}
    >
      <div style={{fontSize: 15, fontWeight: 800, letterSpacing: '0.28em', color: C.muted}}>UNITS</div>
      {removed ? (
        <div style={{marginTop: 4, fontSize: 46, fontWeight: 900, letterSpacing: '0.04em', color: C.red}}>32</div>
      ) : reveal ? (
        <div style={{marginTop: 4, fontSize: 34, fontWeight: 900, letterSpacing: '0.04em'}}>
          <span style={{color: C.cyan}}>32</span>
          <span style={{color: C.muted}}> + </span>
          <span style={{color: C.amber}}>32</span>
        </div>
      ) : (
        <div
          style={{
            marginTop: 2,
            fontSize: 52,
            fontWeight: 900,
            letterSpacing: '0.02em',
            color: C.ink,
          }}
        >
          {count}
        </div>
      )}
      <div style={{marginTop: 6, height: 1, background: 'rgba(255,255,255,0.14)'}} />
    </div>
  );
};

const END_COUNTER = 130;

export const Flash: React.FC<{t: number}> = ({t}) => {
  const events = [...STAGE_TIMES.slice(1), REVEAL];
  let op = 0;
  let color = C.white;
  for (const e of events) {
    const age = t - e;
    if (age >= 0 && age < 0.28) {
      const big = e === REVEAL;
      const v = (1 - age / 0.28) * (big ? 0.38 : 0.16);
      if (v > op) {
        op = v;
        color = big ? C.amber : C.white;
      }
    }
  }
  const beat = beatPulse(t, 9) * 0.035;
  if (op + beat <= 0.001) return null;
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: op > beat ? color : C.cyan,
        opacity: Math.max(op, beat),
        mixBlendMode: 'screen',
        pointerEvents: 'none',
      }}
    />
  );
};

export const Vignette: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      background:
        'radial-gradient(75% 62% at 50% 48%, rgba(0,0,0,0) 38%, rgba(0,0,0,0.62) 100%)',
      pointerEvents: 'none',
    }}
  />
);

export const Scanlines: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      background:
        'repeating-linear-gradient(to bottom, rgba(255,255,255,0.028) 0px, rgba(255,255,255,0.028) 1px, transparent 1px, transparent 4px)',
      opacity: 0.55,
      pointerEvents: 'none',
    }}
  />
);

export const EndCard: React.FC<{t: number}> = ({t}) => {
  const op = smooth((t - 148) / 1.6) * (1 - smooth((t - 151.2) / 0.8));
  if (op <= 0.001) return null;
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: `radial-gradient(60% 40% at 50% 50%, rgba(10,30,40,0.6), rgba(3,5,10,0.96))`,
        opacity: op,
      }}
    >
      <div style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 118, color: C.ink, letterSpacing: '-0.03em', textTransform: 'uppercase'}}>
        DON'T STOP.
      </div>
      <div style={{marginTop: 26, fontFamily: SANS, fontSize: 34, color: C.body}}>别停下来。</div>
    </div>
  );
};

export const TopLine: React.FC<{t: number}> = ({t}) => {
  const p = easeOut(smooth(t / 3));
  return (
    <div
      style={{
        position: 'absolute',
        left: 80,
        right: 80,
        top: 84,
        height: 1,
        background: `linear-gradient(90deg, ${C.cyan}00, ${C.cyan}AA, ${C.cyan}00)`,
        transform: `scaleX(${p})`,
        opacity: 0.5,
      }}
    />
  );
};

export const Kicker: React.FC<{t: number}> = ({t}) => {
  const op = interpolate(t, [0.4, 1.2, 13, 14], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  if (op <= 0.001) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 80,
        top: 108,
        opacity: op,
        fontFamily: DISPLAY,
        fontWeight: 800,
        fontSize: 17,
        letterSpacing: '0.32em',
        textTransform: 'uppercase',
        color: C.muted,
      }}
    >
      <span style={{color: C.cyan, marginRight: 14}}>01</span>
      COMPOUND INTEREST
    </div>
  );
};
