import React from 'react';
import {Composition} from 'remotion';
import {FengShui} from './Film';
import {FengShuiCover} from './Cover';
import {DURATION, FPS, H, W} from './theme';

export const FengShuiRoot: React.FC = () => (
  <>
    <Composition
      id="FengShui"
      component={FengShui}
      durationInFrames={DURATION * FPS}
      fps={FPS}
      width={W}
      height={H}
    />
    <Composition id="FengShuiCover" component={FengShuiCover} durationInFrames={1} fps={FPS} width={W} height={H} />
  </>
);
