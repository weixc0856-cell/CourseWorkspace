import React from 'react';
import {World} from '../carflow/Scene';

export type CarFlowProps = {
  t: number;
  car?: 'drivaer' | 'procedural';
};

// World must sit inside a ThreeCanvas; the composition supplies it.
export const CarFlow: React.FC<CarFlowProps> = (props) => <World {...props} />;
