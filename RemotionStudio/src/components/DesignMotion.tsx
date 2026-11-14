import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {DesignSpec} from '../types';

type Motion = {
  scale: [number, number];
  x: [number, number];
  y: [number, number];
  rotate: [number, number];
};

const STILL: Motion = {scale: [1, 1], x: [0, 0], y: [0, 0], rotate: [0, 0]};

/**
 * Read the visual design's motion intent.  Only the camera string is used
 * here; the rest of the design stays available for engines that can consume
 * it.  The mapping is intentionally conservative: a push, a pull, a pan or a
 * hand-held drift.  Unknown wording means "still", not a guessed move.
 */
export const motionFor = (camera?: string): Motion => {
  const text = (camera || '').toLowerCase();
  if (!text) return STILL;
  if (/(push|zoom in|dolly in|slow push)/.test(text)) {
    return {...STILL, scale: [1, 1.08]};
  }
  if (/(pull out|pull-out|zoom out|dolly out)/.test(text)) {
    return {...STILL, scale: [1.08, 1]};
  }
  if (/pan left/.test(text)) {
    return {...STILL, x: [0, -2.5], scale: [1.02, 1.02]};
  }
  if (/pan right/.test(text)) {
    return {...STILL, x: [0, 2.5], scale: [1.02, 1.02]};
  }
  if (/(orbit|handheld|hand-held|drift)/.test(text)) {
    return {...STILL, rotate: [-0.35, 0.35], scale: [1.02, 1.05]};
  }
  return STILL;
};

export const DesignMotion: React.FC<{
  design?: DesignSpec | null;
  durationInFrames: number;
  children: React.ReactNode;
}> = ({design, durationInFrames, children}) => {
  const frame = useCurrentFrame();
  const motion = motionFor(design?.motion?.camera);
  const [fx, fy] = design?.composition?.focal_point ?? [0.5, 0.5];
  const end = Math.max(1, durationInFrames);
  const scale = interpolate(frame, [0, end], motion.scale, {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const x = interpolate(frame, [0, end], motion.x, {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const y = interpolate(frame, [0, end], motion.y, {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const rotate = interpolate(frame, [0, end], motion.rotate, {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const focus = `${Math.max(0, Math.min(1, fx)) * 100}% ${Math.max(0, Math.min(1, fy)) * 100}%`;
  const child = React.isValidElement(children)
    ? React.cloneElement(children as React.ReactElement<any>, {
        style: {
          ...((children.props as {style?: React.CSSProperties}).style || {}),
          objectPosition: focus,
        },
      })
    : children;

  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          transform: `translate(${x}%, ${y}%) scale(${scale}) rotate(${rotate}deg)`,
          transformOrigin: focus,
        }}
      >
        {child}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
