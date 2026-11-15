import React from 'react';
import {MechanismScene} from '../chapter/MechanismScene';
import type {MechanismDiagramProps} from '../chapter/MechanismScene';

export type {MechanismDiagramProps};

export const MechanismDiagram: React.FC<MechanismDiagramProps> = (props) => <MechanismScene {...props} />;
