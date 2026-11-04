import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {COLORS, FONTS} from '../styles/tokens';
import {Annotation, LegendAnnotation, TextAnnotation} from '../types';
import {secondsToFrames} from '../utils/timing';

const colorFor = (name: TextAnnotation['color']): string => {
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

const useFadeOpacity = (durationInFrames: number): number => {
  const frame = useCurrentFrame();
  if (durationInFrames < 4) return 1;
  const fade = Math.min(9, Math.max(1, Math.floor(durationInFrames / 2)));
  return interpolate(
    frame,
    [0, fade, durationInFrames - fade, durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
};

const TextItem: React.FC<{
  annotation: TextAnnotation;
  durationInFrames: number;
  height: number;
}> = ({annotation, durationInFrames, height}) => {
  const opacity = useFadeOpacity(durationInFrames);
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

const formatValue = (value: number): string => {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2).replace(/\.?0+$/, '');
};

const gradientFor = (annotation: LegendAnnotation, scale: number): string => {
  const stops = [...annotation.stops].sort((left, right) => left[0] - right[0]);
  return `linear-gradient(to top, ${stops
    .map(([position, color]) => {
      const [r, g, b] = color.map((channel) => Math.round(channel * 255));
      return `rgb(${r}, ${g}, ${b}) ${(position * 100).toFixed(1)}%`;
    })
    .join(', ')})`;
};

const LegendItem: React.FC<{
  annotation: LegendAnnotation;
  durationInFrames: number;
  height: number;
}> = ({annotation, durationInFrames, height}) => {
  const opacity = useFadeOpacity(durationInFrames);
  const scale = height / 1080;
  const [x, y] = annotation.position;
  const barWidth = annotation.bar_width * scale;
  const barHeight = annotation.bar_height * scale;
  const labelSize = annotation.label_size * scale;
  const midValue = (annotation.min_value + annotation.max_value) / 2;

  return (
    <AbsoluteFill style={{opacity}}>
      <div
        style={{
          position: 'absolute',
          left: `${x * 100}%`,
          top: `${y * 100}%`,
          display: 'flex',
          alignItems: 'stretch',
          gap: 10 * scale,
          padding: 10 * scale,
          background: 'rgba(255,255,255,0.92)',
          borderLeft: `${Math.max(2, 4 * scale)}px solid ${COLORS.orange}`,
          fontFamily: FONTS.sans,
          color: COLORS.text,
        }}
      >
        <div
          style={{
            width: barWidth,
            height: barHeight,
            background: gradientFor(annotation, scale),
            border: `${Math.max(1, scale)}px solid rgba(0,0,0,0.25)`,
            borderRadius: 3 * scale,
          }}
        />
        <div
          style={{
            height: barHeight,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            fontSize: labelSize,
            lineHeight: 1.1,
            whiteSpace: 'nowrap',
          }}
        >
          <span>
            {formatValue(annotation.max_value)} {annotation.units}
          </span>
          <span>{formatValue(midValue)}</span>
          <span>
            {formatValue(annotation.min_value)} {annotation.units}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const AnnotationItem: React.FC<{
  annotation: Annotation;
  durationInFrames: number;
  height: number;
}> = ({annotation, durationInFrames, height}) => {
  if (annotation.kind === 'legend') {
    return (
      <LegendItem
        annotation={annotation}
        durationInFrames={durationInFrames}
        height={height}
      />
    );
  }
  return (
    <TextItem
      annotation={annotation}
      durationInFrames={durationInFrames}
      height={height}
    />
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
