import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import {C} from './theme';

// KaTeX's display math carries a 1em vertical margin and centres itself.
// Every layout band is measured in fixed pixels, so the margin pushed stacked
// formulas over the band below it (the episode, which had no reset, drew the
// 4× force line through F = ṁΔv). The reset lives with the formula so Chapter
// and Episode render the same box.
const KATEX_RESET = `
  .katex-display { margin: 0 !important; text-align: left !important; }
  .katex { text-align: left !important; }
`;

export const Formula: React.FC<{tex: string; size?: number; color?: string; opacity?: number}> = ({
  tex,
  size = 42,
  color = C.paper,
  opacity = 1,
}) => (
  <>
    <style>{KATEX_RESET}</style>
    <div
      style={{fontSize: size, color, opacity, lineHeight: 1.1}}
      dangerouslySetInnerHTML={{
        __html: katex.renderToString(tex, {displayMode: true, throwOnError: false, strict: false, output: 'html'}),
      }}
    />
  </>
);
