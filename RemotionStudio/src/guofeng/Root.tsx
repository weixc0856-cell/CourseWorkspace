import React from 'react';
import {Composition} from 'remotion';
import {GuofengSample} from './Sample';
import {DUR, FPS, H, W} from './theme';

export const GuofengRoot: React.FC = () => (
  <Composition id="GuofengSample" component={GuofengSample} durationInFrames={DUR} fps={FPS} width={W} height={H} />
);
