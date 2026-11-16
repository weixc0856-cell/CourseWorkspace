import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {CarScene} from '../chapter/CarScene';

const Root: React.FC = () => (
  <>
    <Composition
      id="PreviewCarFlowB4"
      component={CarScene}
      durationInFrames={900}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{
        duration: 30,
        eyebrow: 'T1-01 · 04 / THE NUMBERS',
        headline: 'At 120 km/h the air takes three times the rolling bill.',
      }}
    />
    <Composition
      id="PreviewCarFlowB9"
      component={CarScene}
      durationInFrames={900}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{
        duration: 30,
        eyebrow: 'T1-01 · 09 / WHAT TO KEEP',
        headline: 'Shape is the energy bill.',
      }}
    />
  </>
);
registerRoot(Root);
