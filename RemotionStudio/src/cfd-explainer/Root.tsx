import React from 'react';
import {Composition} from 'remotion';
import {Episode, EpisodeProps} from './Episode';

// Duration/fps come from the shot sidecars carried in inputProps, so this
// root never hard-codes the episode length. Remotion evaluates
// calculateMetadata on the node side with the --props file already parsed.
const emptyProps: EpisodeProps = {shots: []};

export const CfdRoot: React.FC = () => {
  return (
    <Composition
      id="CfdEpisode"
      component={Episode}
      durationInFrames={1}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={emptyProps}
      calculateMetadata={({props}) => {
        const total = props.shots.reduce((a, s) => a + s.n_frames, 0);
        const fps = props.shots.length > 0 ? props.shots[0].fps : 30;
        if (total < 1) {
          throw new Error('cfd-explainer: props.shots is empty -- run episode_build.py first');
        }
        return {...props, durationInFrames: total, fps};
      }}
    />
  );
};
