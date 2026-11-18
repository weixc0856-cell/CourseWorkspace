import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {PhotoScene} from './PhotoScene';
import {CarScene} from './CarScene';
import {MechanismScene} from './MechanismScene';
import {EvidenceScene} from './EvidenceScene';
import {ConclusionScene} from './ConclusionScene';

const FPS = 30;

export type ChapterProps = {
  // The audit fixture passes its own committed images and a procedural car so
  // the regression never depends on public/staging/<slug>/.
  photoImage?: string;
  evidenceImage?: string;
  car?: 'drivaer' | 'procedural';
};

export const Chapter: React.FC<ChapterProps> = ({
  photoImage,
  evidenceImage,
  car = 'drivaer',
}) => (
  <AbsoluteFill style={{background: '#05070A'}}>
    <Sequence from={0} durationInFrames={18 * FPS}>
      <PhotoScene image={photoImage} />
    </Sequence>

    <Sequence from={18 * FPS} durationInFrames={30 * FPS}>
      <CarScene car={car} />
    </Sequence>

    <Sequence from={48 * FPS} durationInFrames={40 * FPS}>
      <MechanismScene />
    </Sequence>

    <Sequence from={88 * FPS} durationInFrames={35 * FPS}>
      <EvidenceScene image={evidenceImage} />
    </Sequence>

    <Sequence from={123 * FPS} durationInFrames={30 * FPS}>
      <ConclusionScene car={car} />
    </Sequence>
  </AbsoluteFill>
);
