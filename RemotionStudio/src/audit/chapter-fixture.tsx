import React from 'react';
import {registerRoot} from 'remotion';
import {Player} from '@remotion/player';
import {Chapter} from '../chapter/Film';

// The code regression must not depend on an episode's staging cache. This
// entry renders the same Chapter component with committed fixtures and the
// procedural car, so `check.ps1` stays green when public/staging is empty.
const params = new URLSearchParams(window.location.search);
const frame = Math.max(0, Number(params.get('frame') ?? '0') || 0);

const AuditRoot: React.FC = () => (
  <Player
    component={Chapter}
    inputProps={{
      photoImage: 'audit-fixtures/chapter-frame.png',
      evidenceImage: 'audit-fixtures/chapter-frame.png',
      car: 'procedural',
    }}
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
