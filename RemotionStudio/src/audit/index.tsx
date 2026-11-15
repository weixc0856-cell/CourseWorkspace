import React from 'react';
import {registerRoot} from 'remotion';
import {Player} from '@remotion/player';
import {Chapter} from '../chapter/Film';

const params = new URLSearchParams(window.location.search);
const frame = Math.max(0, Number(params.get('frame') ?? '0') || 0);

const AuditRoot: React.FC = () => (
  <Player
    component={Chapter}
    durationInFrames={4590}
    fps={30}
    compositionWidth={1920}
    compositionHeight={1080}
    initialFrame={frame}
    controls={false}
    autoPlay={false}
    style={{width: 1920, height: 1080}}
  />
);

registerRoot(AuditRoot);
