import React from 'react';
import {registerRoot} from 'remotion';
import {Player} from '@remotion/player';
import {Episode} from '../episode/Episode';
import timing from '../episode/timing.json';

const params = new URLSearchParams(window.location.search);
const frame = Math.max(0, Number(params.get('frame') ?? '0') || 0);

const AuditRoot: React.FC = () => (
  <Player
    component={Episode}
    durationInFrames={Math.round(timing.total_seconds * timing.fps)}
    fps={timing.fps}
    compositionWidth={1920}
    compositionHeight={1080}
    initialFrame={frame}
    controls={false}
    autoPlay={false}
    style={{width: 1920, height: 1080}}
  />
);

registerRoot(AuditRoot);
