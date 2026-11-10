import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, FONTS} from '../styles/tokens';

export type ChapterCardProps = {
  index: number;
  total: number;
  title: string;
  subtitle?: string;
};

export const ChapterCard: React.FC<ChapterCardProps> = ({index, total, title, subtitle}) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const rise = interpolate(frame, [0, 18], [18, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper, color: COLORS.text}}>
      <div style={{position: 'absolute', left: 128, top: 150, fontFamily: FONTS.sans, fontSize: 24, letterSpacing: 3, color: COLORS.orange}}>
        CHAPTER {String(index).padStart(2, '0')} / {String(total).padStart(2, '0')}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 128,
          top: 210,
          width: 12,
          height: 250,
          backgroundColor: COLORS.orange,
          opacity: fadeIn,
        }}
      />
      <div style={{position: 'absolute', left: 190, top: 250, transform: `translateY(${rise}px)`, opacity: fadeIn}}>
        <div style={{fontFamily: FONTS.serif, fontSize: 92, lineHeight: 1.05, maxWidth: 1420}}>{title}</div>
        {subtitle ? (
          <div style={{marginTop: 34, fontFamily: FONTS.sans, fontSize: 32, color: COLORS.muted, maxWidth: 1180}}>
            {subtitle}
          </div>
        ) : null}
      </div>
      <div style={{position: 'absolute', left: 128, right: 128, bottom: 110, height: 1, backgroundColor: COLORS.divider}} />
    </AbsoluteFill>
  );
};

export const chapterCardDefaults: ChapterCardProps = {
  index: 1,
  total: 5,
  title: 'Why attention',
  subtitle: 'A sequence model that looks at every token at once.',
};
