import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {resolveTheme} from './theme';
import type {PaperHighlightProps} from './types';

const sourceOf = (image: string) =>
  /^(https?:|data:)/.test(image) ? image : staticFile(image);

export const PaperHighlightBox: React.FC<PaperHighlightProps & {themeName?: string}> = ({
  image,
  box,
  label,
  caption,
  source,
  themeName,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const theme = resolveTheme(themeName);
  const vertical = height > width;
  const progress = spring({frame, fps, config: {damping: 200, mass: 0.7}});
  const dim = interpolate(progress, [0, 1], [0, 0.62]);
  const left = `${box.x * 100}%`;
  const top = `${box.y * 100}%`;
  const right = `${(1 - box.x - box.w) * 100}%`;
  const bottom = `${(1 - box.y - box.h) * 100}%`;
  return (
    <AbsoluteFill
      style={{
        background: theme.paper,
        color: theme.ink,
        fontFamily: theme.sans,
        padding: vertical ? '120px 56px 300px' : '64px 120px 150px',
        display: 'flex',
        flexDirection: 'column',
        gap: 24,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{position: 'relative', display: 'inline-block', width: vertical ? '100%' : '74%', maxHeight: '78%'}}>
        <Img
          src={sourceOf(image)}
          style={{display: 'block', width: '100%', height: 'auto', maxHeight: vertical ? 900 : 640, objectFit: 'contain'}}
        />
        <div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
          <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: top, background: `rgba(20,22,26,${dim})`}} />
          <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: bottom, background: `rgba(20,22,26,${dim})`}} />
          <div style={{position: 'absolute', left: 0, top, bottom, width: left, background: `rgba(20,22,26,${dim})`}} />
          <div style={{position: 'absolute', right: 0, top, bottom, width: right, background: `rgba(20,22,26,${dim})`}} />
          <div
            style={{
              position: 'absolute',
              left,
              top,
              width: `${box.w * 100}%`,
              height: `${box.h * 100}%`,
              border: `4px solid ${theme.accent}`,
              boxShadow: `0 0 0 2px rgba(255,255,255,0.7)`,
              opacity: interpolate(progress, [0.2, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
            }}
          />
          {label ? (
            <div
              style={{
                position: 'absolute',
                left,
                top: `calc(${top} - 46px)`,
                background: theme.accent,
                color: theme.white,
                fontSize: 24,
                fontWeight: 700,
                letterSpacing: '0.08em',
                padding: '8px 14px',
                whiteSpace: 'nowrap',
                opacity: interpolate(progress, [0.2, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
              }}
            >
              {label}
            </div>
          ) : null}
        </div>
      </div>
      {caption ? (
        <div style={{fontSize: 30, lineHeight: 1.35, color: theme.body, textAlign: 'center', maxWidth: 1100}}>
          {caption}
        </div>
      ) : null}
      {source ? (
        <div style={{fontSize: 22, color: theme.muted}}>{source}</div>
      ) : null}
    </AbsoluteFill>
  );
};
