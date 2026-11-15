import React from 'react';
import {Composition} from 'remotion';
import {Chapter} from './Film';

export const ChapterRoot: React.FC = () => (
  <Composition id="Chapter" component={Chapter} durationInFrames={4590} fps={30} width={1920} height={1080} />
);
