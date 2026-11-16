import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {assertSequenceDuration} from '../chapter/timing';
import {PhotoScene} from '../chapter/PhotoScene';
import {CarScene} from '../chapter/CarScene';
import {MechanismScene} from '../chapter/MechanismScene';
import {EvidenceScene} from '../chapter/EvidenceScene';
import {Formula} from '../chapter/Formula';
import timing from './timing.json';

const COMPONENTS: Record<string, React.FC<any>> = {
  PhotoInsert: PhotoScene,
  CarFlowScene: CarScene,
  MechanismDiagram: MechanismScene,
  ChartOverlay: EvidenceScene,
  FormulaBlock: (props) => <Formula tex={props.tex} size={props.size ?? 44} />,
};

type Instance = {component: string; duration: number; props?: Record<string, unknown>};
type Beat = {id: string; seconds: number; instances: Instance[]};

export const Episode: React.FC = () => {
  const {fps} = useVideoConfig();
  let cursor = 0;
  const scenes: React.ReactNode[] = [];
  for (const beat of timing.beats as Beat[]) {
    for (const [index, instance] of beat.instances.entries()) {
      const frames = Math.round(instance.duration * fps);
      assertSequenceDuration(frames, fps, instance.duration);
      const Component = COMPONENTS[instance.component];
      if (!Component) throw new Error(`unknown component ${instance.component} in ${beat.id}`);
      const from = cursor;
      scenes.push(
        <Sequence key={`${beat.id}-${index}`} from={from} durationInFrames={frames}>
          <Component {...(instance.props ?? {})} duration={instance.duration} />
        </Sequence>,
      );
      cursor += frames;
    }
  }
  return <AbsoluteFill style={{background: '#05070A'}}>{scenes}</AbsoluteFill>;
};
