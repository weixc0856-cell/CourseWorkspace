import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {WakeDiagram} from '../components/WakeDiagram';

const Root: React.FC = () => (
  <Composition id="PreviewWake" component={WakeDiagram} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={{duration: 5}} />
);
registerRoot(Root);
