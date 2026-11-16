import React from 'react';
import {AbsoluteFill, useVideoConfig} from 'remotion';

// Scenes are authored on a fixed 1920x1080 canvas with absolute pixels. The
// frame scales that canvas to whatever the composition size is, so 480p and
// 1080p renders share one layout instead of collapsing at small sizes.
// Non-16:9 sizes (e.g. 1080x1920 vertical) letterbox at the top-left; they need
// their own centering rule, this frame does not provide one.
export const SceneFrame: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({children, style}) => {
  const {width, height} = useVideoConfig();
  const scale = Math.min(width / 1920, height / 1080);
  return (
    <AbsoluteFill style={{overflow: 'hidden', ...style}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: 1920,
          height: 1080,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
