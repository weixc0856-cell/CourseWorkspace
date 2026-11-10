import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND} from './tokens';
import {Lockup, framesFor, progressBetween} from './BrandMark';
import {fitFontSize, titleStyle} from './layout';
import type {BrandProps} from './types';

/**
 * Course intro — 3.0 s by default.
 *
 * Two elements only: the brand lockup at the top, and the episode title
 * centred. No category number, no translated subtitle, no channel footer.
 *
 * 0.00–0.50  the mark draws
 * 0.35–0.90  WAYNE tracks in
 * 0.75–1.20  title
 * 1.20–3.00  hold
 *
 * The last frame is the held title card. The body is hard-cut in after it —
 * no fade-out, no wipe. A fade left a blank tail and made the cut feel like a
 * dropped frame.
 */
export const CourseIntro: React.FC<BrandProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const total = Math.max(
    1,
    Math.min(durationInFrames, framesFor(props.durationInSeconds ?? 3.0, fps)),
  );
  const scale = total / framesFor(3.0, fps);
  const at = (seconds: number) => Math.round(seconds * fps * scale);

  const draw = progressBetween(frame, at(0), at(0.5));
  const word = progressBetween(frame, at(0.35), at(0.8));
  const track = progressBetween(frame, at(0.35), at(0.9));
  const title = progressBetween(frame, at(0.75), at(1.2));

  const titleText = props.title ?? '';
  const titleSize = fitFontSize(titleText, 1500, [76, 68, 60, 52]);

  return (
    <AbsoluteFill style={{backgroundColor: BRAND.background}}>
      <div
        style={{
          position: 'absolute',
          top: 96,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <Lockup
          variant="compact"
          progress={word}
          taglineProgress={track}
          markProgress={draw}
        />
      </div>

      <div
        style={{
          position: 'absolute',
          top: 500,
          left: 96,
          right: 96,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            ...titleStyle,
            fontSize: titleSize,
            lineHeight: 1.1,
            textAlign: 'center',
            maxWidth: 1500,
            opacity: title,
            transform: `translateY(${(1 - title) * 12}px)`,
          }}
        >
          {titleText}
        </div>
      </div>
    </AbsoluteFill>
  );
};
