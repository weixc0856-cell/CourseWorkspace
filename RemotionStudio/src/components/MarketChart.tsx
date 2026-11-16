import React from 'react';
import {MarketChartScene} from '../chapter/MarketChartScene';
import type {MarketChartProps} from '../chapter/MarketChartScene';

export type {MarketChartProps};

export const MarketChart: React.FC<MarketChartProps> = (props) => <MarketChartScene {...props} />;
