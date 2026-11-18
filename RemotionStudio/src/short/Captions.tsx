import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveTheme} from './theme';
import type {Caption} from './types';

export const Captions: React.FC<{captions: Caption[]; themeName?: string}> = ({
  captions,
  themeName,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const theme = resolveTheme(themeName);
  const seconds = frame / fps;
  const cue = captions.find((item) => seconds >= item.start_s && seconds < item.end_s);
  if (!cue) {
    return null;
  }
  const vertical = height > width;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: vertical ? 40 : 180,
          right: vertical ? 40 : 180,
          bottom: vertical ? 96 : 54,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <div
          style={{
            background: theme.paper,
            border: `2px solid ${theme.border}`,
            boxShadow: '0 6px 24px rgba(0,0,0,0.16)',
            padding: vertical ? '18px 26px' : '14px 30px',
            maxWidth: '100%',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              fontFamily: theme.sans,
              fontSize: vertical ? 38 : 40,
              lineHeight: 1.25,
              color: theme.ink,
              fontWeight: 600,
            }}
          >
            {cue.en}
          </div>
          {cue.zh ? (
            <div
              style={{
                fontFamily: theme.sans,
                fontSize: vertical ? 30 : 32,
                lineHeight: 1.3,
                color: theme.body,
                marginTop: 6,
              }}
            >
              {cue.zh}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
