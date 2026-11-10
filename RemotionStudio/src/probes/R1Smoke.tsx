import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {COLORS, FONTS} from '../styles/tokens';

export const R1Smoke: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const fade = interpolate(
    frame,
    [0, 20, durationInFrames - 20, durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  const lift = interpolate(frame, [0, 30], [24, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper, opacity: fade}}>
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 12,
          backgroundColor: COLORS.orange,
        }}
      />
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          transform: `translateY(${lift}px)`,
          gap: 16,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 84,
            fontWeight: 700,
            color: COLORS.text,
            letterSpacing: -1,
          }}
        >
          R1 engine smoke
        </div>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 36,
            color: COLORS.muted,
          }}
        >
          Remotion render OK
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
