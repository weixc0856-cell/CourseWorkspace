import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {DerivationCard} from '../components/DerivationCard';

const Root: React.FC = () => (
  <Composition id="PreviewDerivation" component={DerivationCard} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={{duration: 5}} />
);
registerRoot(Root);
