import React from 'react';
import {CardScene} from '../chapter/CardScene';
import type {CardProps} from '../chapter/CardScene';
export type {CardProps};
export const Chain: React.FC<CardProps> = (props) => <CardScene {...props} variant="chain" />;
