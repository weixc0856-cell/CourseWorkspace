import React from 'react';
import katex from 'katex';
import {C} from './theme';

export const Formula: React.FC<{tex: string; size?: number; color?: string; opacity?: number}> = ({
  tex,
  size = 42,
  color = C.paper,
  opacity = 1,
}) => (
  <div
    style={{fontSize: size, color, opacity, lineHeight: 1.1}}
    dangerouslySetInnerHTML={{
      __html: katex.renderToString(tex, {displayMode: true, throwOnError: false, strict: false}),
    }}
  />
);
