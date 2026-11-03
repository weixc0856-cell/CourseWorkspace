import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, staticFile} from 'remotion';

type Props = {
  src: string;
  kind: 'image' | 'video';
  useStaticFile?: boolean;
};

export const AccessProbe: React.FC<Props> = ({src, kind, useStaticFile = false}) => {
  const resolved = useStaticFile ? staticFile(src) : src;
  return (
    <AbsoluteFill style={{backgroundColor: '#FFFFFF'}}>
      {kind === 'video' ? (
        <OffthreadVideo
          src={resolved}
          style={{width: '100%', height: '100%', objectFit: 'contain'}}
        />
      ) : (
        <Img
          src={resolved}
          style={{width: '100%', height: '100%', objectFit: 'contain'}}
        />
      )}
    </AbsoluteFill>
  );
};
