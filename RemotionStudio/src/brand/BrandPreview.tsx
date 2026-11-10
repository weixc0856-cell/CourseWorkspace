import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {BRAND} from './tokens';
import {Lockup, framesFor} from './BrandMark';
import {fitFontSize, titleStyle} from './layout';
import {CourseIntro} from './CourseIntro';
import {CourseOutro} from './CourseOutro';
import type {BrandProps} from './types';

/**
 * Review reel: course intro -> a one-page hold -> course outro.
 *
 * Exists so the brand layer can be previewed, rendered and checked on its own
 * (`brand-render`) without a 20-minute lesson build.
 */
export const BrandPreview: React.FC<BrandProps> = (props) => {
  const {fps} = useVideoConfig();
  const intro = framesFor(props.durationInSeconds ?? BRAND.presets.course_intro.duration_s, fps);
  const hold = framesFor(1.5, fps);
  const outro = framesFor(BRAND.presets.course_outro.duration_s, fps);

  return (
    <AbsoluteFill style={{backgroundColor: BRAND.background}}>
      <Sequence durationInFrames={intro} name="brand:intro">
        <CourseIntro {...props} />
      </Sequence>
      <Sequence from={intro} durationInFrames={hold} name="brand:hold">
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
            <Lockup variant="compact" />
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
                fontSize: fitFontSize(props.title ?? '', 1500, [76, 68, 60, 52]),
                lineHeight: 1.1,
                textAlign: 'center',
                maxWidth: 1500,
              }}
            >
              {props.title ?? 'Episode title'}
            </div>
          </div>
        </AbsoluteFill>
      </Sequence>
      <Sequence from={intro + hold} durationInFrames={outro} name="brand:outro">
        <CourseOutro {...props} durationInSeconds={BRAND.presets.course_outro.duration_s} />
      </Sequence>
    </AbsoluteFill>
  );
};
