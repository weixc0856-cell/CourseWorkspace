import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveColor, resolveTheme} from './theme';
import type {CompareSide, SplitCompareProps} from './types';

const Side: React.FC<{
  side: CompareSide;
  align: 'left' | 'right';
  progress: number;
  themeName?: string;
}> = ({side, align, progress, themeName}) => {
  const theme = resolveTheme(themeName);
  const accent = resolveColor(theme, side.accent) || theme.accent;
  const offset = interpolate(progress, [0, 1], [align === 'left' ? -48 : 48, 0]);
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
        opacity: progress,
        transform: `translateX(${offset}px)`,
        alignItems: align === 'right' ? 'flex-end' : 'flex-start',
        textAlign: align,
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          fontSize: 24,
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
          color: accent,
          fontWeight: 700,
        }}
      >
        {side.label}
      </div>
      <div
        style={{
          fontSize: 56,
          lineHeight: 1.08,
          fontWeight: 700,
          color: theme.ink,
        }}
      >
        {side.title}
      </div>
      {(side.points || []).map((point, index) => (
        <div
          key={point}
          style={{
            display: 'flex',
            gap: 14,
            alignItems: 'flex-start',
            maxWidth: 720,
            fontSize: 30,
            lineHeight: 1.35,
            color: theme.body,
            opacity: interpolate(progress, [0.35 + index * 0.18, 1], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            }),
            justifyContent: align === 'right' ? 'flex-end' : 'flex-start',
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              marginTop: 14,
              flex: 'none',
              background: accent,
            }}
          />
          <span>{point}</span>
        </div>
      ))}
    </div>
  );
};

export const SplitCompareCard: React.FC<SplitCompareProps & {themeName?: string}> = ({
  left,
  right,
  verdict,
  themeName,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const theme = resolveTheme(themeName);
  const vertical = height > width;
  const leftProgress = spring({frame, fps, config: {damping: 200, mass: 0.6}});
  const rightProgress = spring({frame: frame - 6, fps, config: {damping: 200, mass: 0.6}});
  return (
    <AbsoluteFill
      style={{
        background: theme.paper,
        color: theme.ink,
        fontFamily: theme.sans,
        padding: vertical ? '180px 64px 240px' : '96px 140px 150px',
        display: 'flex',
        flexDirection: vertical ? 'column' : 'row',
        gap: vertical ? 48 : 64,
        alignItems: 'stretch',
        justifyContent: 'center',
      }}
    >
      <Side side={left} align="left" progress={leftProgress} themeName={themeName} />
      <div
        style={{
          width: vertical ? '100%' : 1,
          height: vertical ? 1 : 'auto',
          background: theme.border,
          flex: 'none',
          alignSelf: 'stretch',
        }}
      />
      <Side
        side={right}
        align={vertical ? 'left' : 'right'}
        progress={rightProgress}
        themeName={themeName}
      />
      {verdict ? (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: vertical ? 220 : 200,
            textAlign: 'center',
            fontSize: 34,
            fontWeight: 700,
            color: theme.accent,
            opacity: interpolate(rightProgress, [0.6, 1], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            }),
          }}
        >
          {verdict}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
