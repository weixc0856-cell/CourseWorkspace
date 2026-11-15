import React from 'react';
import {Formula} from '../chapter/Formula';

export type FormulaBlockProps = {
  tex: string;
  size?: number;
  color?: string;
  opacity?: number;
};

export const FormulaBlock: React.FC<FormulaBlockProps> = (props) => <Formula {...props} />;
