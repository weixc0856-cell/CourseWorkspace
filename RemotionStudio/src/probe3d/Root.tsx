import React from 'react';
import {Composition} from 'remotion';
import {Probe} from './Probe';
export const ProbeRoot: React.FC = () => (
  <Composition id="Probe3D" component={Probe} durationInFrames={30} fps={30} width={1080} height={1920} />
);
