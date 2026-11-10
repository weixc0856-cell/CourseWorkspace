import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND} from './tokens';
import {CenteredLockup, progressBetween} from './BrandMark';
import {bodyStyle, headingStyle} from './layout';
import type {BrandProps} from './types';

/**
 * Course outro — 12 s by default.
 *
 * A sign-off, not a summary. Only the brand lockup, one hairline, the thanks
 * line and the call to action. Course metadata, series names, next-episode
 * teasers and translated slogans are deliberately absent: an end card is a
 * call to action, not a second title page.
 *
 * Everything is on screen by ~1.1 s; the rest is still, because YouTube
 * end-screen elements overlay the last 5–20 s.
 */
export const CourseOutro: React.FC<BrandProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const at = (seconds: number) => Math.round(seconds * fps);
  const fade = (start: number) =>
    progressBetween(frame, at(start), at(start + 0.5));

  const brand = fade(0);
  const thanks = fade(0.4);
  const cta = fade(0.65);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: BRAND.background,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <CenteredLockup
        wordSize={120}
        progress={brand}
        taglineProgress={brand}
        markProgress={brand}
      />

      <div
        style={{
          marginTop: 64,
          width: 96,
          height: 1,
          backgroundColor: BRAND.ink,
          opacity: brand * 0.18,
        }}
      />

      <div
        style={{
          marginTop: 44,
          ...headingStyle,
          fontSize: 44,
          opacity: thanks,
          transform: `translateY(${(1 - thanks) * 8}px)`,
        }}
      >
        {BRAND.identity.thanks}
      </div>

      <div
        style={{
          marginTop: 14,
          ...bodyStyle,
          fontSize: 26,
          color: BRAND.muted,
          opacity: cta,
        }}
      >
        {BRAND.identity.cta}
      </div>
    </AbsoluteFill>
  );
};
