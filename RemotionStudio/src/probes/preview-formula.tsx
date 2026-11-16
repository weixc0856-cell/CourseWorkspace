import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {FormulaBlock} from '../components/FormulaBlock';

const Root: React.FC = () => (
  <Composition id="PreviewFormula" component={FormulaBlock} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={{tex: 'F \propto v^2', title: '1/6 · Why drag rises with speed', duration: 5}} />
);
registerRoot(Root);
