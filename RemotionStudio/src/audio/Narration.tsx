import React from 'react';
import {Audio, staticFile} from 'remotion';
import {stagingPath} from '../utils/timing';

interface Props {
  lesson: string;
  narration: {path: string; duration_s: number} | null;
}

export const Narration: React.FC<Props> = ({lesson, narration}) => {
  if (!narration) return null;
  return <Audio src={staticFile(stagingPath(lesson, narration.path))} />;
};
