import {registerRoot} from 'remotion';
import {Composition} from 'remotion';
import React from 'react';
import {Episode} from './Episode';
import timing from './timing.json';

const Root: React.FC = () => (
  <Composition
    id="Episode"
    component={Episode}
    durationInFrames={Math.round(timing.total_seconds * timing.fps)}
    fps={timing.fps}
    width={1920}
    height={1080}
  />
);

registerRoot(Root);
