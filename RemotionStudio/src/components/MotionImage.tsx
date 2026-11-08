import React from 'react';
import {Img, interpolate, useCurrentFrame} from 'remotion';

export type KenBurnsMotion = {
  kind: 'ken_burns';
  scale_from: number;
  scale_to: number;
  pan_x_from: number;
  pan_x_to: number;
  pan_y_from: number;
  pan_y_to: number;
};

type Props = {
  src: string;
  durationInFrames: number;
  motion: KenBurnsMotion;
};

const imageStyle: React.CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  objectPosition: 'center center',
  transformOrigin: 'center center',
  willChange: 'transform',
};

export const MotionImage: React.FC<Props> = ({src, durationInFrames, motion}) => {
  const frame = useCurrentFrame();
  const last = Math.max(1, durationInFrames - 1);
  const progress = interpolate(frame, [0, last], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const scale = interpolate(progress, [0, 1], [motion.scale_from, motion.scale_to]);
  const translateX = interpolate(progress, [0, 1], [motion.pan_x_from, motion.pan_x_to]);
  const translateY = interpolate(progress, [0, 1], [motion.pan_y_from, motion.pan_y_to]);

  return (
    <Img
      src={src}
      style={{
        ...imageStyle,
        transform: `translate(${translateX}%, ${translateY}%) scale(${scale})`,
      }}
    />
  );
};
