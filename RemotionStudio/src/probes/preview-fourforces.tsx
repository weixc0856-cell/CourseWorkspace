import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {FourForces} from '../components/FourForces';

const Root: React.FC = () => (
  <Composition id="PreviewFourForces" component={FourForces} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={{duration: 5}} />
);
registerRoot(Root);
