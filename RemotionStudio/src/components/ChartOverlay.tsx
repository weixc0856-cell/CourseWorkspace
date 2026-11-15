import React from 'react';
import {EvidenceScene} from '../chapter/EvidenceScene';
import type {ChartOverlayProps} from '../chapter/EvidenceScene';

export type {ChartOverlayProps};

export const ChartOverlay: React.FC<ChartOverlayProps> = (props) => <EvidenceScene {...props} />;
