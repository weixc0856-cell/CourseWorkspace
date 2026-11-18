import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {Captions} from './Captions';
import {MetricBarChart} from './MetricBarChart';
import {PaperHighlightBox} from './PaperHighlightBox';
import {SimpleFlowDiagram} from './SimpleFlowDiagram';
import {SplitCompareCard} from './SplitCompareCard';
import {StatementScene} from './StatementScene';
import {resolveTheme} from './theme';
import type {ShortScene, ShortStoryboardProps} from './types';

const Scene: React.FC<{scene: ShortScene; themeName?: string}> = ({scene, themeName}) => {
  switch (scene.kind) {
    case 'split_compare':
      return <SplitCompareCard {...scene.props} themeName={themeName} />;
    case 'paper_highlight':
      return <PaperHighlightBox {...scene.props} themeName={themeName} />;
    case 'metric_bar':
      return <MetricBarChart {...scene.props} themeName={themeName} />;
    case 'simple_flow':
      return <SimpleFlowDiagram {...scene.props} themeName={themeName} />;
    case 'statement':
      return <StatementScene {...scene.props} themeName={themeName} />;
    default:
      return null;
  }
};

export const ShortStoryboard: React.FC<ShortStoryboardProps> = (props) => {
  const {fps, width, height} = useVideoConfig();
  const theme = resolveTheme(props.theme);
  let cursor = 0;
  return (
    <AbsoluteFill style={{background: theme.paper}}>
      {props.audio ? <Audio src={staticFile(props.audio)} /> : null}
      {props.scenes.map((scene) => {
        const frames = Math.max(1, Math.round(scene.duration_s * fps));
        const from = cursor;
        cursor += frames;
        return (
          <Sequence key={scene.id} from={from} durationInFrames={frames} name={scene.id}>
            <Scene scene={scene} themeName={props.theme} />
          </Sequence>
        );
      })}
      {props.captions && props.captions.length > 0 ? (
        <Captions captions={props.captions} themeName={props.theme} />
      ) : null}
      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          border: `10px solid ${theme.paper}`,
          boxSizing: 'border-box',
        }}
      />
    </AbsoluteFill>
  );
};
