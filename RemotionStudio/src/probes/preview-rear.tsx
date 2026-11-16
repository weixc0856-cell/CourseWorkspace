import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {RearShapeDiagram} from '../components/RearShapeDiagram';

const Root: React.FC = () => (
  <Composition id="PreviewRear" component={RearShapeDiagram} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={{duration: 5}} />
);
registerRoot(Root);
