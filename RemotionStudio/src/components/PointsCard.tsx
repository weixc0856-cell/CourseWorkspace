import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT} from '../chapter/theme';

export type PointsCardProps = {
  title?: string;
  eyebrow?: string;
  points?: string[];
  footer?: string;
  note?: string;
  duration?: number;
};

const DEFAULT_POINTS = [
  'Above ~60 km/h, air becomes the largest road load.',
  'Drag grows with v²; the power to beat it grows with v³.',
  'Most drag is pressure, and most of it happens at the rear.',
  'Shape sets cD; frontal area multiplies it.',
  'The shape is a compromise with people, safety, cooling and design.',
];

// The conclusion of T1-01 is five ideas, so the last stretch of the episode
// needs a card that lists them. A mechanism diagram under the title "Five
// things to keep" showed the 2× speed derivation instead of the five points.
export const PointsCard: React.FC<PointsCardProps> = ({
  title = 'Five ideas to keep',
  eyebrow = 'T1-01 · 09 / WHAT TO KEEP',
  points = DEFAULT_POINTS,
  footer = 'WHY A CAR NEEDS AERODYNAMICS',
  note = 'one compromise · five consequences',
  duration = 24,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = Math.min(1, frame / fps / Math.max(duration, 0.1));
  const scale = 1 + 0.004 * progress;
  return (
    <SceneFrame
      style={{
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 96,
          color: C.orange,
          fontSize: 18,
          fontWeight: 600,
          letterSpacing: '0.26em',
        }}
      >
        {eyebrow}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 138,
          width: 1200,
          transform: `translateY(${(1 - progress) * 8}px) scale(${scale})`,
          transformOrigin: 'left top',
          fontFamily: DISPLAY,
          fontSize: 54,
          fontWeight: 600,
          letterSpacing: '-0.03em',
          color: C.paper,
        }}
      >
        {title}
      </div>

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 280,
          display: 'flex',
          flexDirection: 'column',
          gap: 26,
        }}
      >
        {points.map((point, index) => {
          const appear = Math.min(1, Math.max(0, (progress * 9 - index) * 3));
          return (
            <div
              key={point}
              style={{
                display: 'flex',
                gap: 28,
                alignItems: 'baseline',
                opacity: appear,
                transform: `translateY(${(1 - appear) * 10}px)`,
              }}
            >
              <span
                style={{
                  fontFamily: DISPLAY,
                  fontSize: 30,
                  fontWeight: 600,
                  color: C.orange,
                  minWidth: 56,
                }}
              >
                {String(index + 1).padStart(2, '0')}
              </span>
              <span style={{fontSize: 29, lineHeight: 1.35, color: C.paper}}>{point}</span>
            </div>
          );
        })}
      </div>

      <div style={{position: 'absolute', left: 96, top: 716, width: 1500}}>
        <div style={{height: 2, background: 'rgba(244,241,234,0.14)', marginBottom: 16}} />
        <div style={{color: 'rgba(244,241,234,0.75)', fontSize: 24}}>{note}</div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          bottom: 130,
          display: 'flex',
          justifyContent: 'space-between',
          color: 'rgba(244,241,234,0.38)',
          fontSize: 15,
          letterSpacing: '0.12em',
        }}
      >
        <span>{footer}</span>
        <span>SYNTHESIS · Ch. 3 §3.1–3.2.6</span>
      </div>
    </SceneFrame>
  );
};
