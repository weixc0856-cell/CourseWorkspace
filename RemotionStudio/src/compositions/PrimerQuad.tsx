import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {COLORS, FONTS} from '../styles/tokens';

export type QuadPanel = {
  seed: number;
  path: string;
  caption?: string;
};

export type PrimerQuadProps = {
  title: string;
  subtitle?: string;
  panels: QuadPanel[];
  total_frames: number;
};

const Cell: React.FC<{panel: QuadPanel}> = ({panel}) => (
  <div
    style={{
      position: 'relative',
      overflow: 'hidden',
      border: `1px solid ${COLORS.border}`,
      background: COLORS.surface,
    }}
  >
    <OffthreadVideo
      src={staticFile(panel.path)}
      muted
      style={{width: '100%', height: '100%', objectFit: 'cover'}}
    />
    <div
      style={{
        position: 'absolute',
        left: 18,
        top: 14,
        padding: '5px 12px',
        background: 'rgba(251,250,247,0.9)',
        color: COLORS.ink,
        fontFamily: FONTS.sans,
        fontSize: 20,
        letterSpacing: 1,
      }}
    >
      seed {panel.seed}
      {panel.caption ? ` · ${panel.caption}` : ''}
    </div>
  </div>
);

export const PrimerQuad: React.FC<PrimerQuadProps> = ({title, subtitle, panels}) => (
  <AbsoluteFill style={{backgroundColor: COLORS.paper, color: COLORS.ink}}>
    <div style={{position: 'absolute', left: 72, top: 56, fontFamily: FONTS.serif, fontSize: 54}}>
      {title}
    </div>
    {subtitle ? (
      <div style={{position: 'absolute', left: 74, top: 126, fontFamily: FONTS.sans, fontSize: 22, color: COLORS.muted}}>
        {subtitle}
      </div>
    ) : null}
    <div
      style={{
        position: 'absolute',
        left: 72,
        right: 72,
        top: 190,
        bottom: 64,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gridTemplateRows: '1fr 1fr',
        gap: 24,
      }}
    >
      {panels.slice(0, 4).map((panel) => (
        <Cell key={panel.seed} panel={panel} />
      ))}
    </div>
  </AbsoluteFill>
);

export const primerQuadDefaults: PrimerQuadProps = {
  title: 'Four seeds, one rule set',
  subtitle: 'Rock-paper-scissors agents on a hex grid; deterministic worlds.',
  total_frames: 900,
  panels: [
    {seed: 7, path: 'staging/primer-quad/world-7.mp4'},
    {seed: 11, path: 'staging/primer-quad/world-11.mp4'},
    {seed: 13, path: 'staging/primer-quad/world-13.mp4'},
    {seed: 17, path: 'staging/primer-quad/world-17.mp4'},
  ],
};
