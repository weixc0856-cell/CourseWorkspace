import React from 'react';
import {CarScene} from '../chapter/CarScene';
import type {CarFlowSceneProps} from '../chapter/CarScene';

export type {CarFlowSceneProps};

export const CarFlowScene: React.FC<CarFlowSceneProps> = (props) => <CarScene {...props} />;
