import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

/**
 * HUD for the aging plate, drawn by Remotion instead of being baked into the
 * captured world. The payload comes from `collect` (compose.overlay:
 * aging_hud) and carries one sample per recorded simulation frame.
 */
export type AgingHudSegment = {
  id: string;
  label: string;
  start: number;
  end: number;
  population: number[];
  mean_age: (number | null)[];
  mutation: number[];
  hazard: number[][];
};

export type AgingHudOverlay = {
  kind: 'aging_hud';
  title: string;
  split: number;
  total: number;
  fps: number;
  segments: AgingHudSegment[];
};

type Sample = {
  population: number;
  meanAge: number | null;
  mutation: number;
  hazard: number[];
};

const sampleAt = (segment: AgingHudSegment, time: number): Sample => {
  const count = segment.population.length;
  if (count === 0) {
    return {population: 0, meanAge: null, mutation: 0, hazard: []};
  }
  const span = Math.max(0.001, segment.end - segment.start);
  const progress = Math.min(1, Math.max(0, (time - segment.start) / span));
  const exact = progress * (count - 1);
  const index = Math.min(count - 1, Math.floor(exact));
  const next = Math.min(count - 1, index + 1);
  const mix = exact - index;
  const lerp = (a: number, b: number) => a + (b - a) * mix;

  const ageA = segment.mean_age[index];
  const ageB = segment.mean_age[next];
  const meanAge =
    ageA == null && ageB == null
      ? null
      : lerp(ageA ?? ageB ?? 0, ageB ?? ageA ?? 0);

  const hazardA = segment.hazard[index] ?? [];
  const hazardB = segment.hazard[next] ?? hazardA;
  const hazard = hazardA.map((value, bin) => lerp(value, hazardB[bin] ?? value));

  return {
    population: Math.round(lerp(segment.population[index], segment.population[next])),
    meanAge,
    mutation: lerp(segment.mutation[index], segment.mutation[next]),
    hazard,
  };
};

const COLORS = {
  ink: '#e8eef2',
  label: '#9fb0ba',
  muted: '#7f909a',
  danger: '#e8733b',
  safe: '#8fb48a',
  young: '#6e8f6a',
  old: '#c06a3a',
  panel: 'rgba(10,13,15,0.94)',
};

const HazardChart: React.FC<{
  values: number[];
  color: string;
  height: number;
}> = ({values, color, height}) => {
  const width = 340;
  const peak = Math.max(0.02, ...values);
  const points = values.map((value, index) => {
    const x = (index / Math.max(1, values.length - 1)) * width;
    const y = height - Math.min(1, value / peak) * (height - 6) - 3;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {[0, 1, 2, 3, 4].map((line) => (
        <line
          key={line}
          x1={0}
          x2={width}
          y1={(height * line) / 4}
          y2={(height * line) / 4}
          stroke="rgba(160,175,186,0.25)"
          strokeWidth={1}
        />
      ))}
      {points.length > 1 ? (
        <polyline points={points.join(' ')} fill="none" stroke={color} strokeWidth={2} />
      ) : null}
      <text x={2} y={11} fill="rgba(220,228,233,0.55)" fontSize={10} fontFamily="Arial, sans-serif">
        risk of death by age
      </text>
    </svg>
  );
};

export const AgingHud: React.FC<{overlay: AgingHudOverlay}> = ({overlay}) => {
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const time = frame / fps;
  const segment =
    overlay.segments.find((item) => time >= item.start && time < item.end) ??
    overlay.segments[overlay.segments.length - 1];
  const sample = sampleAt(segment, time);
  const scale = height / 1080;
  const accent = segment.id === 'danger' ? COLORS.danger : COLORS.safe;

  const stat = (label: string, value: string) => (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        paddingTop: 12 * scale,
      }}
    >
      <span style={{fontSize: 12 * scale, color: COLORS.label}}>{label}</span>
      <span style={{fontSize: 26 * scale, fontWeight: 600}}>{value}</span>
    </div>
  );

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          bottom: 180 * scale,
          width: '31%',
          maxWidth: 430 * scale,
          boxSizing: 'border-box',
          padding: `${28 * scale}px ${26 * scale}px ${20 * scale}px`,
          background: `linear-gradient(90deg, rgba(10,13,15,0) 0%, rgba(10,13,15,0.86) 12%, ${COLORS.panel} 100%)`,
          color: COLORS.ink,
          fontFamily: 'Arial, sans-serif',
          display: 'flex',
          flexDirection: 'column',
          gap: 18 * scale,
        }}
      >
        <h1 style={{margin: 0, fontSize: 15 * scale, fontWeight: 600, letterSpacing: '0.02em', color: '#cfd9df'}}>
          {overlay.title}
        </h1>
        <div style={{fontSize: 22 * scale, fontWeight: 700, color: accent}}>{segment.label}</div>
        {stat('population', String(sample.population))}
        {stat('mean age at death', sample.meanAge == null ? '—' : String(Math.round(sample.meanAge)))}
        {stat('late-acting mutations / agent', sample.mutation.toFixed(1))}
        <div style={{marginTop: 2 * scale}}>
          <HazardChart values={sample.hazard} color={accent} height={150 * scale} />
        </div>
        <div style={{fontSize: 11 * scale, color: COLORS.muted, lineHeight: 1.5}}>
          Agent-based model. Every blob carries a genome, ages and reproduces.
          <br />
          <br />
          <span style={{display: 'inline-block', width: 9 * scale, height: 9 * scale, borderRadius: '50%', marginRight: 5 * scale, background: COLORS.young}} />
          young
          <span style={{display: 'inline-block', width: 9 * scale, height: 9 * scale, borderRadius: '50%', margin: `0 ${5 * scale}px 0 ${12 * scale}px`, background: COLORS.old}} />
          old
        </div>
      </div>
    </AbsoluteFill>
  );
};
