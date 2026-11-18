import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveTheme} from './theme';
import type {StatementProps} from './types';

const SIZES = {
  hero: 132,
  large: 92,
  normal: 64,
} as const;

export const StatementScene: React.FC<StatementProps & {themeName?: string}> = ({
  kicker,
  text,
  emphasis,
  sub,
  align,
  size,
  themeName,
}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const theme = resolveTheme(themeName);
  const vertical = height > width;
  const scale = SIZES[size || 'hero'] * (vertical ? 1.15 : 1);
  const rise = interpolate(frame, [0, 10], [18, 0], {extrapolateRight: 'clamp'});
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const parts = emphasis ? text.split(emphasis) : [text];
  return (
    <AbsoluteFill
      style={{
        background: theme.paper,
        color: theme.ink,
        fontFamily: theme.sans,
        padding: vertical ? '180px 64px 300px' : '110px 150px 170px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: align === 'left' ? 'flex-start' : 'center',
        textAlign: align || 'center',
        gap: 28,
      }}
    >
      {kicker ? (
        <div
          style={{
            fontSize: 26,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            fontWeight: 700,
            color: theme.accent,
          }}
        >
          {kicker}
        </div>
      ) : null}
      <div
        style={{
          fontSize: scale,
          fontWeight: 700,
          lineHeight: 1.06,
          letterSpacing: '-0.01em',
          opacity,
          transform: `translateY(${rise}px)`,
          maxWidth: 1500,
        }}
      >
        {emphasis && parts.length > 1 ? (
          <>
            {parts[0]}
            <span style={{color: theme.accent}}>{emphasis}</span>
            {parts.slice(1).join(emphasis)}
          </>
        ) : (
          text
        )}
      </div>
      {sub ? (
        <div
          style={{
            fontSize: size === 'normal' ? 34 : 42,
            lineHeight: 1.4,
            color: theme.body,
            maxWidth: 1200,
            opacity: interpolate(frame, [8, 20], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            }),
          }}
        >
          {sub}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
