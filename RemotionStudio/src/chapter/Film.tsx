import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {PhotoScene} from './PhotoScene';
import {CarScene} from './CarScene';
import {MechanismScene} from './MechanismScene';
import {EvidenceScene} from './EvidenceScene';
import {ConclusionScene} from './ConclusionScene';

const FPS = 30;

export const Chapter: React.FC = () => (
  <AbsoluteFill style={{background: '#05070A'}}>
    <style>{`
      .katex-display { margin: 0 !important; text-align: left !important; }
      .katex { text-align: left !important; }
    `}</style>

    <Sequence from={0} durationInFrames={18 * FPS}>
      <PhotoScene />
    </Sequence>

    <Sequence from={18 * FPS} durationInFrames={30 * FPS}>
      <CarScene />
    </Sequence>

    <Sequence from={48 * FPS} durationInFrames={40 * FPS}>
      <MechanismScene />
    </Sequence>

    <Sequence from={88 * FPS} durationInFrames={35 * FPS}>
      <EvidenceScene />
    </Sequence>

    <Sequence from={123 * FPS} durationInFrames={30 * FPS}>
      <ConclusionScene />
    </Sequence>
  </AbsoluteFill>
);
