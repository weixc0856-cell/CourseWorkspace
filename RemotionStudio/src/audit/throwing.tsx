import React from 'react';
import {AbsoluteFill, registerRoot} from 'remotion';
import {Player} from '@remotion/player';

// Negative fixture for frame-audit: a component throws during render. The
// audit must report page_error with this text, never "0 issues".
const Boom: React.FC = () => {
  throw new Error('audit selftest: deliberate render error');
};

const Safe: React.FC = () => (
  <AbsoluteFill style={{background: '#0B1119'}}>
    <div style={{position: 'absolute', left: 300, top: 300, color: '#F4F1EA', fontSize: 60}}>
      never rendered
    </div>
  </AbsoluteFill>
);

const AuditRoot: React.FC = () => (
  <Player
    component={Boom}
    errorFallback={() => <Safe />}
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
