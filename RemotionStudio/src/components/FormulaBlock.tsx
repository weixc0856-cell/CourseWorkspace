import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {Formula} from '../chapter/Formula';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT} from '../chapter/theme';

export type FormulaBlockProps = {
  tex: string;
  title?: string;
  eyebrow?: string;
  footer?: string;
  size?: number;
  color?: string;
  opacity?: number;
  duration?: number;
};

// A formula card holds one line. A very slow push (0.5% over its duration)
// keeps a 20 s card from being a dead frame without inventing motion.
//
// The card carries the same frame as the other episode scenes: the lesson
// eyebrow, a background gradient and a footer. Without them the derivation
// beat was 130 s of an almost empty near-black screen, which reads as a dead
// frame and trips the black-interval gate.
export const FormulaBlock: React.FC<FormulaBlockProps> = ({
  tex,
  title,
  eyebrow = 'T1-01 · 04 / THE DERIVATION',
  footer = 'WHY A CAR NEEDS AERODYNAMICS',
  size = 104,
  color = C.paper,
  opacity = 1,
  duration = 10,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = Math.min(1, frame / fps / Math.max(duration, 0.1));
  const scale = 1 + 0.005 * progress;
  return (
    <SceneFrame
      style={{
        opacity,
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 96,
          color: C.orange,
          fontSize: 18,
          fontWeight: 600,
          letterSpacing: '0.26em',
        }}
      >
        {eyebrow}
      </div>

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 300,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          transform: `scale(${scale})`,
          transformOrigin: 'center 30%',
        }}
      >
        {title ? (
          <div
            style={{
              fontFamily: DISPLAY,
              fontSize: 30,
              fontWeight: 600,
              letterSpacing: '0.08em',
              color: C.orange,
              marginBottom: 56,
              textAlign: 'center',
            }}
          >
            {title}
          </div>
        ) : null}
        <div
          style={{
            width: '100%',
            height: 2,
            background: 'rgba(244,241,234,0.14)',
            marginBottom: 72,
          }}
        />
        <Formula tex={tex} size={size} color={color} />
      </div>

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          bottom: 130,
          display: 'flex',
          justifyContent: 'space-between',
          color: 'rgba(244,241,234,0.38)',
          fontSize: 15,
          letterSpacing: '0.12em',
        }}
      >
        <span>{footer}</span>
        <span>SCHEMATIC · FROM THE MOMENTUM MODEL</span>
      </div>
    </SceneFrame>
  );
};
