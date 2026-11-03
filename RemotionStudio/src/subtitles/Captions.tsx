import React, {useEffect, useState} from 'react';
import {
  AbsoluteFill,
  continueRender,
  delayRender,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {COLORS, FONTS} from '../styles/tokens';
import {Cue, parseSrt, stagingPath} from '../utils/timing';

interface Props {
  lesson: string;
  subtitles: {path: string; cues: number} | null;
}

export const Captions: React.FC<Props> = ({lesson, subtitles}) => {
  const [cues, setCues] = useState<Cue[] | null>(null);
  const [handle] = useState(() =>
    subtitles ? delayRender('load subtitles') : null,
  );
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  useEffect(() => {
    if (!subtitles || handle === null) return;
    let cancelled = false;
    fetch(staticFile(stagingPath(lesson, subtitles.path)))
      .then((response) => {
        if (!response.ok) {
          throw new Error(`subtitle fetch failed: ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        if (cancelled) return;
        setCues(parseSrt(text));
        continueRender(handle);
      })
      .catch(() => {
        if (cancelled) return;
        setCues([]);
        continueRender(handle);
      });
    return () => {
      cancelled = true;
    };
  }, [handle, lesson, subtitles]);

  if (!subtitles || !cues) return null;

  const current = frame / fps;
  const cue = cues.find((item) => current >= item.start && current < item.end);
  if (!cue) return null;

  return (
    <AbsoluteFill
      style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 64}}
    >
      <div
        style={{
          background: 'rgba(255,255,255,0.92)',
          color: COLORS.text,
          fontFamily: FONTS.sans,
          fontSize: 36,
          lineHeight: 1.4,
          padding: '18px 28px',
          borderLeft: `4px solid ${COLORS.orange}`,
          maxWidth: '80%',
          textAlign: 'center',
          whiteSpace: 'pre-wrap',
        }}
      >
        {cue.text}
      </div>
    </AbsoluteFill>
  );
};
