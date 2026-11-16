import React from 'react';
import {registerRoot} from 'remotion';
import {AbsoluteFill} from 'remotion';
import {Player} from '@remotion/player';

// Negative fixture for frame-audit: a composition that renders the background
// only. The audit must report blank_frame instead of "0 issues".
const Blank: React.FC = () => <AbsoluteFill style={{background: '#05070A'}} />;

const AuditRoot: React.FC = () => (
  <Player
    component={Blank}
    durationInFrames={300}
    fps={30}
    compositionWidth={1920}
    compositionHeight={1080}
    initialFrame={30}
    controls={false}
    autoPlay={false}
    style={{width: 1920, height: 1080}}
  />
);

registerRoot(AuditRoot);
