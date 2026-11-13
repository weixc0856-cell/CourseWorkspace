import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, DISPLAY, FPS, beatPulse} from '../theme';

const NOISE =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='160' height='160' filter='url(%23n)' opacity='0.55'/></svg>\")";

export const Backdrop: React.FC<{accent?: string}> = ({accent = C.cyan}) => (
  <AbsoluteFill
    style={{
      background: `
        radial-gradient(70% 45% at 50% 26%, rgba(20,52,68,0.65) 0%, rgba(6,12,18,0) 70%),
        radial-gradient(50% 35% at 82% 72%, rgba(76,40,120,0.28) 0%, rgba(5,7,12,0) 70%),
        radial-gradient(40% 30% at 12% 64%, ${accent}14 0%, rgba(5,7,12,0) 72%),
        linear-gradient(180deg, #060A10 0%, #05070C 55%, #03050A 100%)
      `,
    }}
  >
    <AbsoluteFill
      style={{
        backgroundImage:
          'linear-gradient(rgba(95,243,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(95,243,255,0.045) 1px, transparent 1px)',
        backgroundSize: '72px 72px',
        maskImage: 'radial-gradient(70% 60% at 50% 45%, black 0%, transparent 100%)',
        WebkitMaskImage: 'radial-gradient(70% 60% at 50% 45%, black 0%, transparent 100%)',
      }}
    />
  </AbsoluteFill>
);

export const Grain: React.FC = () => (
  <AbsoluteFill
    style={{
      backgroundImage: NOISE,
      backgroundSize: '160px 160px',
      opacity: 0.075,
      mixBlendMode: 'overlay',
      pointerEvents: 'none',
    }}
  />
);

export const Scanlines: React.FC = () => (
  <AbsoluteFill
    style={{
      background: 'repeating-linear-gradient(to bottom, rgba(255,255,255,0.035) 0px, rgba(255,255,255,0.035) 1px, transparent 1px, transparent 4px)',
      opacity: 0.5,
      pointerEvents: 'none',
    }}
  />
);

export const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background: 'radial-gradient(75% 60% at 50% 46%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.55) 100%)',
      pointerEvents: 'none',
    }}
  />
);

export const CutFlash: React.FC<{color?: string}> = ({color = C.cyan}) => {
  const frame = useCurrentFrame();
  const a = interpolate(frame, [0, 2, 7], [0.5, 0.16, 0], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill
      style={{backgroundColor: color, opacity: a, mixBlendMode: 'screen', pointerEvents: 'none'}}
    />
  );
};

export const BeatVignette: React.FC<{color?: string}> = ({color = C.cyan}) => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const p = beatPulse(t, 9);
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(55% 40% at 50% 50%, ${color}${Math.round(10 + p * 14).toString(16).padStart(2, '0')} 0%, rgba(0,0,0,0) 70%)`,
        mixBlendMode: 'screen',
        pointerEvents: 'none',
        opacity: 0.8,
      }}
    />
  );
};

export const ProgressLine: React.FC<{color?: string}> = ({color = C.cyan}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const p = frame / Math.max(1, durationInFrames - 1);
  return (
    <div style={{position: 'absolute', left: 80, right: 80, bottom: 46, height: 18}}>
      <div style={{position: 'absolute', left: 0, right: 0, top: 8, height: 1, background: 'rgba(255,255,255,0.12)'}} />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 7,
          height: 3,
          width: `${p * 100}%`,
          background: color,
          boxShadow: `0 0 12px ${color}`,
          borderRadius: 2,
        }}
      />
    </div>
  );
};

export const Timecode: React.FC<{color?: string}> = ({color = C.muted}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const fmt = (f: number) => {
    const s = Math.floor(f / FPS);
    return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  };
  return (
    <div
      style={{
        position: 'absolute',
        right: 80,
        bottom: 96,
        fontFamily: DISPLAY,
        fontWeight: 800,
        fontSize: 17,
        letterSpacing: '0.22em',
        color,
      }}
    >
      {fmt(frame)} / {fmt(durationInFrames)}
    </div>
  );
};

export const BottomMark: React.FC<{text: string; color?: string}> = ({text, color = C.faint}) => (
  <div
    style={{
      position: 'absolute',
      left: 80,
      bottom: 96,
      fontFamily: DISPLAY,
      fontWeight: 800,
      fontSize: 16,
      letterSpacing: '0.24em',
      color,
      textTransform: 'uppercase',
    }}
  >
    {text}
  </div>
);
