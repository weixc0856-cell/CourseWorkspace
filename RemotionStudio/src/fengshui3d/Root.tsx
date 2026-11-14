import React from 'react';
import {Composition} from 'remotion';
import {FengShui3D} from './Film';

export const FengShui3DRoot: React.FC = () => (
  <Composition id="FengShui3D" component={FengShui3D} durationInFrames={4560} fps={30} width={1080} height={1920} />
);
