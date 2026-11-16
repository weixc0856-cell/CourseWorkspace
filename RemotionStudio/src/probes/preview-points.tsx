import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {PointsCard} from '../components/PointsCard';

const Root: React.FC = () => (
  <Composition id="PreviewPoints" component={PointsCard} durationInFrames={730} fps={30} width={1920} height={1080} defaultProps={{duration: 24.293}} />
);
registerRoot(Root);
