import React from 'react';
import {Composition} from 'remotion';
import {Compound} from './Compound';
export const CompoundRoot: React.FC = () => (
  <Composition
    id="CompoundInterest"
    component={Compound}
    durationInFrames={4560}
    fps={30}
    width={1080}
    height={1920}
  />
);
