import React from 'react';
import {AbsoluteFill, Audio, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {Scene} from './Scene';
import {
  Caption,
  Flash,
  Headline,
  Kicker,
  Scanlines,
  TopLine,
  Vignette,
} from './Overlay';
import {C, FPS} from './timeline';

export const Compound: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  return (
    <AbsoluteFill style={{backgroundColor: C.bg}}>
      <Audio src={staticFile('vibe/we-never-128.m4a')} />
      <ThreeCanvas
        width={1080}
        height={1920}
        dpr={1}
        camera={{fov: 38, position: [8, 5.4, 10], near: 0.1, far: 80}}
        gl={{antialias: true, alpha: false}}
      >
        <Scene t={t} />
      </ThreeCanvas>

      <Kicker t={t} />
      <TopLine t={t} />

      <Headline
        lines={['START WITH ONE.']}
        start={0.8}
        end={9.2}
        t={t}
        size={94}
        accent="ONE"
        accentColor={C.cyan}
      />
      <Headline
        lines={['DOUBLE.']}
        start={11.25}
        end={15.8}
        t={t}
        size={132}
        accent="DOUBLE."
        accentColor={C.cyan}
      />
      <Headline
        lines={['64.']}
        start={48.75}
        end={54.2}
        t={t}
        size={196}
        accent="64."
        accentColor={C.cyan}
        top={100}
      />
      <Headline
        lines={['THE LAST', 'DOUBLING.']}
        start={54.375}
        end={59.5}
        t={t}
        size={82}
        accent="DOUBLING."
        accentColor={C.amber}
        top={120}
      />
      <Headline
        lines={['= EVERYTHING', 'BEFORE IT.']}
        start={60.0}
        end={72.5}
        t={t}
        size={86}
        accent="BEFORE"
        accentColor={C.amber}
        top={126}
      />
      <Headline
        lines={['STOP ONE STEP', 'EARLY.']}
        start={78.75}
        end={89.0}
        t={t}
        size={82}
        accent="EARLY."
        accentColor={C.red}
        top={126}
      />
      <Headline
        lines={['YOU LOSE', 'HALF.']}
        start={90.0}
        end={101.0}
        t={t}
        size={116}
        accent="HALF."
        accentColor={C.red}
        top={132}
      />
      <Headline
        lines={['PUT IT BACK.']}
        start={103.125}
        end={112.5}
        t={t}
        size={94}
        accent="BACK."
        accentColor={C.cyan}
        top={126}
      />
      <Headline
        lines={['THE LAST STEP', 'IS THE WHOLE STORY.']}
        start={118.125}
        end={129.0}
        t={t}
        size={66}
        accent="WHOLE"
        accentColor={C.cyan}
        top={130}
      />
      <Headline
        lines={['COMPOUND INTEREST', 'IS BACK-LOADED.']}
        start={131.25}
        end={143.0}
        t={t}
        size={66}
        accent="BACK-LOADED."
        accentColor={C.amber}
        top={126}
      />
      <Headline
        lines={["DON'T STOP."]}
        start={144.375}
        end={151.0}
        t={t}
        size={120}
        accent="STOP."
        accentColor={C.cyan}
        top={770}
      />

      <Caption zh="从一个开始。" start={1} end={9.2} t={t} />
      <Caption zh="翻倍。" start={11.25} end={15.8} t={t} />
      <Caption zh="六十四。" start={48.75} end={54.2} t={t} />
      <Caption zh="最后一次翻倍，等于前面所有翻倍之和。" start={54.375} end={72.5} t={t} color={C.amber} />
      <Caption zh="少走一步。" start={78.75} end={89.0} t={t} color={C.red} />
      <Caption zh="结果少一半。" start={90.0} end={101.0} t={t} color={C.red} />
      <Caption zh="把它放回去。" start={103.125} end={112.5} t={t} />
      <Caption zh="最后一步，就是全部。" start={118.125} end={129.0} t={t} />
      <Caption zh="复利，是后置的。" start={131.25} end={143.0} t={t} color={C.amber} />
      <Caption zh="别停下来。" start={144.375} end={151.0} t={t} />

      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(46% 18% at 50% 42%, rgba(5,7,12,0.72), rgba(5,7,12,0) 70%)',
          opacity:
            Math.max(0, Math.min(1, (t - 145) / 0.7)) *
            (1 - Math.max(0, Math.min(1, (t - 151.2) / 0.6))),
        }}
      />
      <Flash t={t} />
      <Vignette />
      <Scanlines />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: '#000',
          opacity: interpolate(t, [151.1, 152], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
        }}
      />
    </AbsoluteFill>
  );
};
