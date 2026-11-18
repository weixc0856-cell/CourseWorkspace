import React from 'react';
import {AbsoluteFill} from 'remotion';
import tokens from '../../../shared/design-tokens/tokens.json';
import layout from '../../../shared/design-tokens/swatch-layout.json';

/**
 * One-frame colour reference shared with the Manim proof.
 *
 * The layout and the colour keys come from shared/design-tokens, so a pixel
 * sampled at the same cell can be compared across engines. No labels and no
 * animation: this frame exists to be measured, not watched.
 */
export const TokenSwatch: React.FC = () => {
  const colors = tokens.colors as Record<string, string>;
  const stepX = layout.cell.w + layout.gap;
  const stepY = layout.cell.h + layout.gap;
  return (
    <AbsoluteFill style={{backgroundColor: colors.paper}}>
      {layout.keys.map((key, index) => {
        const col = index % layout.columns;
        const row = Math.floor(index / layout.columns);
        return (
          <div
            key={key}
            data-token-key={key}
            style={{
              position: 'absolute',
              left: layout.origin.x + col * stepX,
              top: layout.origin.y + row * stepY,
              width: layout.cell.w,
              height: layout.cell.h,
              backgroundColor: colors[key],
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
