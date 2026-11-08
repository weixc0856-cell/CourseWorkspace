import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

export type FormulaProps = {
  latex: string;
  displayMode?: boolean;
  color?: string;
  fontSize?: number;
  align?: 'left' | 'center';
};

export const Formula: React.FC<FormulaProps> = ({
  latex,
  displayMode = true,
  color = '#E8EEF7',
  fontSize = 48,
  align = 'center',
}) => {
  const html = katex.renderToString(latex, {
    displayMode,
    throwOnError: true,
    strict: 'error',
    output: 'html',
    trust: false,
  });
  return (
    <div
      style={{
        color,
        fontSize,
        lineHeight: 1.25,
        textAlign: align,
        width: '100%',
      }}
      dangerouslySetInnerHTML={{__html: html}}
    />
  );
};
