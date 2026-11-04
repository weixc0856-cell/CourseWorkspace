import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {COLORS, FONTS} from '../styles/tokens';
import {Annotation} from '../types';
import {secondsToFrames} from '../utils/timing';

const colorFor = (name: Annotation['color']): string => {
  switch (name) {
    case 'muted':
      return COLORS.muted;
    case 'orange':
      return COLORS.orange;
    case 'white':
      return COLORS.white;
    default:
      return COLORS.text;
  }
};

const AnnotationItem: React.FC<{
  annotation: Annotation;
  durationInFrames: number;
  height: number;
}> = ({annotation, durationInFrames, height}) => {
  const frame = useCurrentFrame();
  const fade = Math.min(9, Math.max(1, Math.floor(durationInFrames / 2)));
  const opacity =
    durationInFrames < 4
      ? 1
      : interpolate(
          frame,
          [0, fade, durationInFrames - fade, durationInFrames],
          [0, 1, 1, 0],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
        );
  const [x, y] = annotation.position;
  const translateX =
    annotation.align === 'center'
      ? '-50%'
      : annotation.align === 'right'
        ? '-100%'
        : '0%';

  return (
    <AbsoluteFill style={{opacity}}>
      <div
        style={{
          position: 'absolute',
          left: `${x * 100}%`,
          top: `${y * 100}%`,
          transform: `translateX(${translateX})`,
          maxWidth: '80%',
          fontFamily: FONTS.sans,
          fontSize: annotation.size * (height / 1080),
          lineHeight: 1.25,
          color: colorFor(annotation.color),
          textAlign: annotation.align,
          whiteSpace: 'pre-wrap',
          background: annotation.background
            ? 'rgba(255,255,255,0.92)'
            : 'transparent',
          padding: annotation.background ? '10px 16px' : 0,
          borderLeft: annotation.background
            ? `4px solid ${COLORS.orange}`
            : undefined,
        }}
      >
        {annotation.text}
      </div>
    </AbsoluteFill>
  );
};

export const Annotations: React.FC<{
  annotations: Annotation[] | null | undefined;
}> = ({annotations}) => {
  const {fps, height} = useVideoConfig();
  if (!annotations || annotations.length === 0) return null;

  return (
    <AbsoluteFill>
      {annotations.map((annotation) => {
        const from = secondsToFrames(annotation.start_s, fps);
        const durationInFrames = Math.max(
          1,
          secondsToFrames(annotation.duration_s, fps),
        );
        return (
          <Sequence
            key={annotation.id}
            from={from}
            durationInFrames={durationInFrames}
            name={`${annotation.id}:annotation`}
          >
            <AnnotationItem
              annotation={annotation}
              durationInFrames={durationInFrames}
              height={height}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
