import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND} from './tokens';
import {CenteredLockup, progressBetween} from './BrandMark';
import {labelStyle} from './layout';
import type {BrandProps} from './types';

/**
 * Shorts signature — 0–1 s, 9:16.
 *
 * English only: lockup plus the English category. No title, no translation.
 * A short gets a signature, not a compressed long-video outro.
 */
export const ShortSignature: React.FC<BrandProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fadeIn = progressBetween(frame, 0, Math.max(1, Math.round(0.18 * fps)));

  return (
    <AbsoluteFill
      style={{
        backgroundColor: BRAND.background,
        justifyContent: 'center',
        alignItems: 'center',
        opacity: fadeIn,
      }}
    >
      <CenteredLockup
        wordSize={64}
        progress={fadeIn}
        taglineProgress={fadeIn}
        markProgress={fadeIn}
      />
      {props.category ? (
        <div style={{marginTop: 56}}>
          <div style={{...labelStyle, opacity: fadeIn}}>{props.category}</div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
