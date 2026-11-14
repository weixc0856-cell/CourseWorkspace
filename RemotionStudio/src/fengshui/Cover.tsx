import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {DISPLAY, P, SANS} from './theme';
import {Landscape, Village} from './components/Landscape';
import {SERIES_EN, SERIES_ZH} from './data';

const KAI = '"STKaiti", "KaiTi", "Adobe Kaiti Std", serif';

export const FengShuiCover: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: P.paper}}>
    <Img
      src={staticFile('fengshui/paper.png')}
      style={{position: 'absolute', inset: 0, width: 1080, height: 1920, opacity: 0.85, objectFit: 'cover'}}
    />
    <AbsoluteFill
      style={{background: 'radial-gradient(78% 62% at 50% 42%, rgba(245,240,230,0) 42%, rgba(191,182,162,0.28) 100%)'}}
    />
    <div style={{position: 'absolute', inset: 0, transform: 'scale(1.02)', transformOrigin: '50% 80%'}}>
      <Landscape t={4} draw={1} farDraw={1} riverDraw={1} strata={1} />
      <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
        <Village p={1} />
      </svg>
    </div>

    <div
      style={{
        position: 'absolute',
        left: 84,
        right: 84,
        top: 96,
        fontFamily: DISPLAY,
        fontSize: 18,
        letterSpacing: '0.26em',
        color: P.inkFaint,
        display: 'flex',
        justifyContent: 'space-between',
      }}
    >
      <span>EP 01 / 08</span>
      <span>{SERIES_EN}</span>
    </div>
    <div style={{position: 'absolute', left: 84, right: 84, top: 140, height: 1, background: P.ink, opacity: 0.12}} />

    <div style={{position: 'absolute', left: 96, top: 250, display: 'flex', alignItems: 'flex-start', gap: 34}}>
      {['风', '水'].map((c, i) => (
        <div key={i} style={{fontFamily: KAI, fontSize: 300, lineHeight: 1.02, color: P.ink}}>
          {c}
        </div>
      ))}
    </div>
    <div style={{position: 'absolute', left: 96, top: 640, width: 300, height: 1, background: P.ink, opacity: 0.35}} />
    <div
      style={{
        position: 'absolute',
        left: 96,
        top: 672,
        fontFamily: SANS,
        fontSize: 52,
        color: P.ink,
        letterSpacing: '0.02em',
      }}
    >
      风水为什么叫风水？
    </div>
    <div
      style={{
        position: 'absolute',
        left: 96,
        top: 760,
        fontFamily: DISPLAY,
        fontWeight: 400,
        fontSize: 24,
        letterSpacing: '0.24em',
        color: P.inkSoft,
      }}
    >
      WHY IT IS CALLED WIND-WATER
    </div>

    <div
      style={{
        position: 'absolute',
        left: 760,
        top: 470,
        width: 150,
        height: 150,
        background: P.cinnabar,
        transform: 'rotate(-3deg)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        outline: `3px solid ${P.cinnabar}`,
        outlineOffset: 4,
      }}
    >
      {['风', '水'].map((c, i) => (
        <span key={i} style={{fontFamily: '"STSong", "SimSun", serif', fontSize: 64, color: P.paper, lineHeight: 1.04}}>
          {c}
        </span>
      ))}
    </div>

    <div
      style={{
        position: 'absolute',
        left: 84,
        right: 84,
        bottom: 92,
        fontFamily: KAI,
        fontSize: 40,
        color: P.ink,
      }}
    >
      {SERIES_ZH}
    </div>
  </AbsoluteFill>
);
