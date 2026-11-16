import React from 'react';
import {AbsoluteFill, registerRoot} from 'remotion';
import {Player} from '@remotion/player';

// Positive fixture for frame-audit: one instance declares the beat and asset
// the timeline expects, so beat_id/asset_mismatch must stay quiet.
const Instance: React.FC = () => (
  <AbsoluteFill style={{background: '#0B1119', color: '#F4F1EA'}}>
    <div
      data-beat-id="B1"
      data-instance-index={0}
      data-asset-src="fig-1.67.png"
      style={{position: 'absolute', inset: 0}}
    >
      <div style={{position: 'absolute', left: 300, top: 300, fontSize: 80}}>Instance fixture</div>
    </div>
  </AbsoluteFill>
);

const AuditRoot: React.FC = () => (
  <Player
    component={Instance}
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
