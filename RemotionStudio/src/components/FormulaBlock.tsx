import React from 'react';
import {SceneFrame} from '../chapter/SceneFrame';
import {Formula} from '../chapter/Formula';

export type FormulaBlockProps = {
  tex: string;
  size?: number;
  color?: string;
  opacity?: number;
};

// A formula on its own card. The 96 px padding is the safe area (docs/生产合同.md
// §9): rendering the KaTeX output without a container put wide formulas past the
// margins, which the frame audit caught as safe_area overflow.
export const FormulaBlock: React.FC<FormulaBlockProps> = ({size = 64, ...rest}) => (
  <SceneFrame>
    <div
      style={{
        position: 'absolute',
        left: 96,
        right: 96,
        top: 96,
        bottom: 96,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{maxWidth: '100%'}}>
        <Formula {...rest} size={size} />
      </div>
    </div>
  </SceneFrame>
);
