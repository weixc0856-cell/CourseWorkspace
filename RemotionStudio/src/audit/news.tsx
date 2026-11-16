import React from 'react';
import {registerRoot} from 'remotion';
import {Player} from '@remotion/player';
import {NewsEpisode, defaultNewsProps} from '../news/NewsEpisode';

const params = new URLSearchParams(window.location.search);
const frame = Math.max(0, Number(params.get('frame') ?? '0') || 0);

const AuditRoot: React.FC = () => (
  <Player
    component={NewsEpisode}
    inputProps={defaultNewsProps}
    durationInFrames={Math.round(defaultNewsProps.duration_s * defaultNewsProps.fps)}
    fps={defaultNewsProps.fps}
    compositionWidth={1920}
    compositionHeight={1080}
    initialFrame={frame}
    controls={false}
    autoPlay={false}
    style={{width: 1920, height: 1080}}
  />
);

registerRoot(AuditRoot);
