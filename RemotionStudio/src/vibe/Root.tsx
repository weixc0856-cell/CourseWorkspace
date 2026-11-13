import React from 'react';
import {Composition} from 'remotion';
import {VibeEtch} from './VibeEtch';
import {FPS, H, W} from './theme';

export const VibeRoot: React.FC = () => (
  <Composition
    id="VibeEtch"
    component={VibeEtch}
    durationInFrames={4560}
    fps={FPS}
    width={W}
    height={H}
  />
);
