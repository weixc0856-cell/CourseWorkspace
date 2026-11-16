import {useCurrentFrame, useVideoConfig} from 'remotion';

// Clamp a component's internal clock to its declared duration.
// The animation plays within `duration` seconds and then holds its last frame;
// when a beat needs more time, it is split into several instances instead of
// stretching one animation into slow motion.
export const useSceneTime = (durationSeconds?: number): number => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seconds = frame / fps;
  if (!durationSeconds || durationSeconds <= 0) return seconds;
  // Clamp, do not scale: the animation plays within `duration` and then holds
  // its final state. A longer sequence therefore produces a real static hold,
  // which static_hold flags and forces the beat to be split into instances.
  return Math.min(seconds, durationSeconds);
};

export const assertSequenceDuration = (
  durationInFrames: number,
  fps: number,
  durationSeconds: number,
): void => {
  const actual = durationInFrames / fps;
    // 0.02 s is below one frame at 30 fps (1/30 = 0.033 s): rounding an
  // instance duration to whole frames cannot make a real mismatch pass.
  if (Math.abs(actual - durationSeconds) > 0.02) {
    throw new Error(
      `sequence is ${actual}s but the instance declares ${durationSeconds}s; split the beat into instances instead of stretching one`,
    );
  }
};
