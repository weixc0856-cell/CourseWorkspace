import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Formula} from '../components/Formula';

export type FormulaProbeProps = {
  latex: string;
  label?: string;
};

export const FormulaProbe: React.FC<FormulaProbeProps> = ({
  latex,
  label = 'Formula pipeline · KaTeX',
}) => {
  return (
    <AbsoluteFill style={{backgroundColor: '#0B1220', fontFamily: 'Arial, sans-serif'}}>
      <div style={{position: 'absolute', left: 120, top: 100, color: '#4CC2FF', fontSize: 24, letterSpacing: 2}}>
        {label.toUpperCase()}
      </div>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', padding: 160}}>
        <div style={{color: '#E8EEF7'}}>
          <Formula latex={latex} fontSize={64} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
