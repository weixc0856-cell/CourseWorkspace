import React from 'react';
import {PhotoScene} from '../chapter/PhotoScene';
import type {PhotoInsertProps} from '../chapter/PhotoScene';

export type {PhotoInsertProps};

export const PhotoInsert: React.FC<PhotoInsertProps> = (props) => <PhotoScene {...props} />;
