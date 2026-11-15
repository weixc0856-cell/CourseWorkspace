import React from 'react';
import {Composition} from 'remotion';
import {CarFlow} from './Film';

export const CarFlowRoot: React.FC = () => (
  <Composition id="CarFlow" component={CarFlow} durationInFrames={900} fps={30} width={1920} height={1080} />
);
