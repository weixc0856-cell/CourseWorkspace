import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type SceneBeat = {
  at_s: number;
  text: string;
  accent?: boolean;
};

export type ScenePageProps = {
  page: number;
  total_pages: number;
  section: string;
  title: string;
  formula?: string;
  beats: SceneBeat[];
  duration_s: number;
  accent?: string;
};

const INK = '#E8EEF7';
const MUTED = '#8494A8';
const BG = '#0B1220';

const clamp = (v: number) => Math.max(0, Math.min(1, v));

const FlowLines: React.FC<{t: number; accent: string}> = ({t, accent}) => {
  const lines = [0, 1, 2, 3, 4, 5, 6];
  return (
    <svg
      width="1920"
      height="1080"
      viewBox="0 0 1920 1080"
      style={{position: 'absolute', inset: 0, opacity: 0.10}}
    >
      {lines.map((i) => {
        const y = 180 + i * 105 + Math.sin(t * 0.25 + i) * 14;
        return (
          <path
            key={i}
            d={`M -100 ${y} C 420 ${y - 40}, 860 ${y + 46}, 2020 ${y - 10}`}
            fill="none"
            stroke={i === 3 ? accent : INK}
            strokeWidth={i === 3 ? 2.4 : 1.2}
          />
        );
      })}
    </svg>
  );
};

export const ScenePage: React.FC<ScenePageProps> = ({
  page,
  total_pages,
  section,
  title,
  formula,
  beats,
  accent = '#4CC2FF',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const ordered = [...beats].sort((a, b) => a.at_s - b.at_s);
  let current = 0;
  for (let i = 0; i < ordered.length; i++) {
    if (t >= ordered[i].at_s) current = i;
  }
  const beat = ordered[current];
  const prev = current > 0 ? ordered[current - 1] : null;
  const enter = clamp((t - beat.at_s) / 0.7);
  const rise = (1 - enter) * 34;

  const titleIn = interpolate(t, [0, 0.8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const size = beat.text.length > 78 ? 50 : beat.text.length > 54 ? 58 : 70;

  return (
    <AbsoluteFill style={{backgroundColor: BG, fontFamily: 'Arial, Helvetica, sans-serif'}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 72% 34%, rgba(76,194,255,0.13), rgba(11,18,32,0) 55%)',
        }}
      />
      <FlowLines t={t} accent={accent} />

      <div style={{position: 'absolute', left: 110, top: 86, opacity: titleIn}}>
        <div
          style={{
            color: accent,
            fontSize: 22,
            letterSpacing: 3.2,
            textTransform: 'uppercase',
            fontWeight: 600,
          }}
        >
          {section} · {String(page).padStart(2, '0')}/{String(total_pages).padStart(2, '0')}
        </div>
        <div style={{color: INK, fontSize: 54, fontWeight: 700, marginTop: 14}}>
          {title}
        </div>
        <div style={{height: 3, width: 430, background: accent, marginTop: 18, opacity: 0.85}} />
      </div>

      {formula ? (
        <div
          style={{
            position: 'absolute',
            right: 110,
            top: 120,
            color: accent,
            fontSize: 34,
            borderLeft: `3px solid ${accent}`,
            paddingLeft: 22,
            opacity: titleIn * 0.95,
          }}
        >
          {formula}
        </div>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: 110,
          right: 110,
          top: 330,
          height: 540,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
        }}
      >
        {prev ? (
          <div
            style={{
              color: MUTED,
              fontSize: 34,
              lineHeight: 1.25,
              marginBottom: 26,
              opacity: 0.55,
              maxWidth: 1450,
            }}
          >
            {prev.text}
          </div>
        ) : null}
        <div
          style={{
            color: beat.accent ? accent : INK,
            fontSize: size,
            lineHeight: 1.14,
            fontWeight: beat.accent ? 700 : 500,
            maxWidth: 1520,
            opacity: enter,
            transform: `translateY(${rise}px)`,
          }}
        >
          {beat.text}
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 110,
          right: 110,
          bottom: 152,
          height: 3,
          background: 'rgba(232,238,247,0.14)',
        }}
      >
        <div
          style={{
            height: 3,
            width: `${clamp(t / Math.max(0.1, ordered[ordered.length - 1].at_s + 6)) * 100}%`,
            background: accent,
            opacity: 0.65,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
