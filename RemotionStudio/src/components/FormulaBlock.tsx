import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Formula} from '../chapter/Formula';

export type FormulaBlockProps = {
  tex: string;
  title?: string;
  size?: number;
  color?: string;
  opacity?: number;
  duration?: number;
};

// A formula card holds one line. A very slow push (0.5% over its duration)
// keeps a 20 s card from being a dead frame without inventing motion.
export const FormulaBlock: React.FC<FormulaBlockProps> = ({
  tex,
  title,
  size = 44,
  color,
  opacity = 1,
  duration = 10,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = Math.min(1, frame / fps / Math.max(duration, 0.1));
  const scale = 1 + 0.005 * progress;
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity}}>
      <div style={{transform: `scale(${scale})`}}>
        {title ? (
          <div style={{fontSize: 18, letterSpacing: '0.26em', color: '#E8733B', marginBottom: 18, textAlign: 'center'}}>
            {title}
          </div>
        ) : null}
        <Formula tex={tex} size={size} color={color} />
      </div>
    </AbsoluteFill>
  );
};
