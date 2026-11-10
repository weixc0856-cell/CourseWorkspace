import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND} from './tokens';
import {CenteredLockup, progressBetween} from './BrandMark';
import {CANVAS, Hairline, bodyStyle, headingStyle, labelStyle, microStyle} from './layout';
import type {BrandProps} from './types';

/**
 * News outro — 6 s by default.
 *
 * News has no intro: narration starts on frame 0. The end card carries the
 * English category, the real date, the brand and one call to action. No
 * translation, no episode metadata.
 */
export const NewsOutro: React.FC<BrandProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const at = (seconds: number) => Math.round(seconds * fps);
  const fade = (start: number) =>
    progressBetween(frame, at(start), at(start + 0.45));

  const brand = fade(0);
  const copy = fade(0.35);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: BRAND.background,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      {props.category ? (
        <div style={{position: 'absolute', left: CANVAS.margin, top: 96}}>
          <div style={{...labelStyle, opacity: brand}}>{props.category}</div>
        </div>
      ) : null}
      {props.date ? (
        <div
          style={{
            position: 'absolute',
            right: CANVAS.margin,
            top: 96,
            ...microStyle,
            opacity: brand,
          }}
        >
          {props.date}
        </div>
      ) : null}
      <Hairline top={176} opacity={brand} />

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

      <div style={{marginTop: 44, ...headingStyle, fontSize: 44, opacity: copy}}>
        {BRAND.identity.thanks}
      </div>
      <div
        style={{
          marginTop: 14,
          ...bodyStyle,
          fontSize: 26,
          color: BRAND.muted,
          opacity: copy,
        }}
      >
        {BRAND.identity.cta}
      </div>
    </AbsoluteFill>
  );
};
