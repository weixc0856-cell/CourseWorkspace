import React from 'react';
import * as THREE from 'three';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {BPM, DISPLAY, clamp01, easeOut, lerp} from '../fengshui/theme';
import {CAPTIONS, EPISODE_ZH, SERIES_EN, SERIES_ZH, T} from '../fengshui/data';
import fig from '../fengshui/figure.json';
import {World} from './Scene';
import {Big3, Caption3, Quote3, Seal3, Small3, T3, useT} from './Type3D';

const PROFILE = (fig as unknown as {profile: {x: number[]; speed: number[]}; ratios: {crest: number; lee: number}}).profile;
const RATIOS = (fig as unknown as {ratios: {crest: number; lee: number}}).ratios;

const Win: React.FC<{t: number; a: number; b: number; children: React.ReactNode}> = ({t, a, b, children}) => {
  if (t < a || t >= b) return null;
  const o = Math.min(1, (t - a) / 0.25) * Math.min(1, (b - t) / 0.22);
  return <div style={{position: 'absolute', inset: 0, opacity: o}}>{children}</div>;
};

const Readout: React.FC<{t: number; start: number}> = ({t, start}) => {
  const p = easeOut(clamp01((t - start) / 0.8));
  if (p <= 0) return null;
  const w = 420;
  const h = 120;
  const xmin = PROFILE.x[0];
  const xmax = PROFILE.x[PROFILE.x.length - 1];
  const ymax = 2.3;
  const px = (v: number) => ((v - xmin) / (xmax - xmin)) * w;
  const py = (v: number) => h - (v / ymax) * h;
  const count = Math.max(2, Math.floor(PROFILE.x.length * p));
  const pts = PROFILE.x.slice(0, count).map((vx, i) => `${px(vx).toFixed(1)},${py(PROFILE.speed[i]).toFixed(1)}`).join(' L');
  return (
    <div
      style={{
        position: 'absolute',
        left: 84,
        top: 1330,
        width: w + 40,
        padding: '18px 20px 14px',
        background: 'rgba(8,18,19,0.72)',
        border: `1px solid ${T3.gold}33`,
        opacity: p,
      }}
    >
      <div style={{fontFamily: DISPLAY, fontSize: 15, letterSpacing: '0.24em', color: T3.muted}}>
        SIMULATION · 2D CROSS-SECTION
      </div>
      <svg width={w} height={h} style={{display: 'block', marginTop: 12}}>
        <line x1={0} y1={py(1)} x2={w} y2={py(1)} stroke={T3.muted} strokeOpacity={0.35} strokeDasharray="5 6" />
        <path d={`M${pts}`} fill="none" stroke={T3.gold} strokeWidth={2} strokeLinejoin="round" />
        <circle cx={px(8)} cy={py(RATIOS.crest)} r={3.4} fill={T3.gold} />
        <circle cx={px(10.6)} cy={py(RATIOS.lee)} r={3.4} fill={T3.cinnabar} />
      </svg>
      <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: DISPLAY, fontSize: 16, letterSpacing: '0.14em', marginTop: 6}}>
        <span style={{color: T3.gold}}>CREST {RATIOS.crest.toFixed(1)}×</span>
        <span style={{color: T3.cinnabar}}>LEE {RATIOS.lee.toFixed(1)}×</span>
        <span style={{color: T3.muted}}>1 M ABOVE GROUND</span>
      </div>
    </div>
  );
};

const EndCard3: React.FC<{t: number; start: number}> = ({t, start}) => {
  const p = easeOut(clamp01((t - start) / 1.1));
  if (p <= 0) return null;
  return (
    <>
      <AbsoluteFill style={{background: `rgba(6,13,14,${0.9 * p})`}} />
      <div style={{position: 'absolute', left: 84, top: 620, opacity: p}}>
        <div style={{fontFamily: DISPLAY, fontSize: 19, letterSpacing: '0.32em', color: T3.gold}}>EP 01</div>
        <div style={{height: 26}} />
        <div style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 88, lineHeight: 0.96, letterSpacing: '-0.03em', color: T3.paper}}>
          WHY IT IS
          <br />
          CALLED
          <br />
          <span style={{color: T3.gold}}>WIND-WATER</span>
        </div>
        <div style={{height: 34}} />
        <div style={{fontFamily: DISPLAY, fontSize: 18, letterSpacing: '0.2em', color: T3.muted, lineHeight: 1.8}}>
          {SERIES_EN}
          <br />
          EPISODE ONE OF EIGHT
        </div>
        <div style={{height: 22}} />
        <div style={{fontFamily: '"STKaiti", "KaiTi", serif', fontSize: 38, color: T3.paper}}>{SERIES_ZH}</div>
        <div style={{fontFamily: '"NotoSCVibe", sans-serif', fontSize: 22, color: T3.muted, marginTop: 6}}>{EPISODE_ZH}</div>
      </div>
      <Seal3 chars="风水" start={start + 1.3} top={1320} left={780} size={140} />
      <div
        style={{
          position: 'absolute',
          left: 84,
          right: 84,
          bottom: 90,
          fontFamily: DISPLAY,
          fontSize: 15,
          letterSpacing: '0.14em',
          color: T3.faint,
          lineHeight: 1.9,
          opacity: p,
        }}
      >
        《葬书》内篇 · 旧题晋郭璞　·　FLOW FIELD: 2D SIMULATION, SCHEMATIC
        <br />
        MUSIC: GUZHENG MORNING — ANTTI LUODE, CC BY 3.0
      </div>
    </>
  );
};

export const FengShui3D: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / 30;
  const bar = Math.floor((t * BPM) / 240) + 1;

  const stampT = T.name + 1.5;
  const since = t - stampT;
  const shake = since >= 0 && since < 0.6 ? Math.exp(-since * 9) * Math.sin(since * 70) : 0;
  const wind = Math.min(clamp01((t - 1.5) / 2.5), 1 - clamp01((t - (T.end - 2)) / 3));
  const bloom = 0.6 + 0.35 * wind + 0.2 * (t > T.sim && t < T.water ? 1 : 0);

  return (
    <AbsoluteFill style={{backgroundColor: T3.ink}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(120% 78% at 64% 56%, #1d3537 0%, #14272a 30%, #0c1a1c 58%, #070f11 82%, #050b0c 100%)',
        }}
      />
      <Audio src={staticFile('fengshui/wind-water-126.m4a')} />
      <ThreeCanvas
        shadows
        width={1080}
        height={1920}
        dpr={2}
        camera={{fov: 38, position: [-46, 40, 66], near: 0.4, far: 420}}
        gl={{antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.62}}
      >
        <World t={t} wind={wind * 0.92} shake={shake} bloom={bloom} />
      </ThreeCanvas>

      {/* legibility scrims */}
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(to bottom, rgba(6,13,14,0.9) 0%, rgba(6,13,14,0.62) 24%, rgba(6,13,14,0.12) 46%, rgba(6,13,14,0) 62%)',
        }}
      />
      <AbsoluteFill
        style={{
          background: 'linear-gradient(to top, rgba(6,13,14,0.88) 0%, rgba(6,13,14,0.25) 16%, rgba(6,13,14,0) 30%)',
        }}
      />

      {/* hook */}
      <Win t={t} a={T.hook} b={T.question}>
        <div style={{position: 'absolute', left: 96, top: 330, display: 'flex', gap: 40}}>
          {['风', '水'].map((c, i) => {
            const p = easeOut(clamp01((t - 0.3 - i * 0.7) / 1.1));
            return (
              <div key={i} style={{overflow: 'hidden', height: 330}}>
                <div
                  style={{
                    fontFamily: '"STKaiti", "KaiTi", serif',
                    fontSize: 300,
                    lineHeight: 1.06,
                    color: T3.paper,
                    transform: `translateY(${(1 - p) * 30}%)`,
                    opacity: p,
                    textShadow: `0 0 60px ${T3.gold}33`,
                  }}
                >
                  {c}
                </div>
              </div>
            );
          })}
        </div>
        <Small3 text="WIND · WATER" start={2.4} top={720} size={26} />
        <Caption3 zh={CAPTIONS.hook[0].zh} start={2.2} />
      </Win>

      <Win t={t} a={T.question} b={T.earlier}>
        <Big3 lines={['WHERE DOES THE', 'WORD COME FROM?']} start={T.question + 0.15} size={88} top={262} accent="WORD COME FROM?" />
        <Small3 text="EARLIEST EXTANT USE: A BURIAL MANUAL" start={T.question + 1.1} top={520} />
        <Caption3 zh={CAPTIONS.question[0].zh} start={T.question + 0.5} />
      </Win>

      <Win t={t} a={T.earlier} b={T.quote}>
        <Big3 lines={['BEFORE THE WORD,', 'THE PRACTICE.']} start={T.earlier + 0.1} size={84} top={262} accent="THE PRACTICE." />
        <div style={{position: 'absolute', left: 84, top: 520, fontFamily: '"STKaiti", "KaiTi", serif', fontSize: 46, color: T3.paper, opacity: 0.92}}>
          《诗经·大雅·公刘》 相其阴阳，观其流泉
        </div>
        <Small3 text="SHI JING · GONG LIU · WESTERN ZHOU" start={T.earlier + 1.2} top={606} />
        <Caption3 zh={CAPTIONS.earlier[0].zh} start={T.earlier + 0.6} />
      </Win>

      <Win t={t} a={T.quote} b={T.ridge}>
        <Quote3 columns={['气乘风则散', '界水则止']} start={T.quote + 0.2} top={300} size={92} />
        <Big3 lines={['QI SCATTERS', 'IN WIND.', 'IT STOPS', 'AT WATER.']} start={T.quote + 0.8} size={54} top={430} right={604} />
        <Small3 text={'《葬书》内篇 · 旧题晋郭璞 (276–324)\nBOOK OF BURIAL · INNER CHAPTER'} start={T.quote + 2.2} top={900} />
        <Caption3 zh={CAPTIONS.quote[0].zh} start={T.quote + 0.6} />
      </Win>

      <Win t={t} a={T.ridge} b={T.sim}>
        <Big3 lines={['A RIDGE IS A WALL.']} start={T.ridge + 0.1} size={92} top={250} accent="WALL." />
        <Small3 text="ONE CROSS-SECTION, TWO DRAWINGS" start={T.ridge + 0.9} top={380} />
        <Caption3 zh={CAPTIONS.ridge[0].zh} start={T.ridge + 0.5} />
      </Win>

      <Win t={t} a={T.sim} b={T.water}>
        <Big3 lines={['BEHIND IT,', 'THE WIND DROPS.']} start={T.sim + 0.1} size={64} top={220} accent="THE WIND DROPS." />
        <Readout t={t} start={T.sim + 0.5} />
        <Caption3 zh={CAPTIONS.sim[0].zh} start={T.sim + 0.3} end={T.chart} />
        <Caption3 zh={CAPTIONS.chart[0].zh} start={T.chart + 0.2} />
      </Win>

      <Win t={t} a={T.water} b={T.village}>
        <Big3 lines={['WATER STOPS', 'WHAT WIND', 'SCATTERS.']} start={T.water + 0.1} size={80} top={250} accent="SCATTERS." />
        <Caption3 zh={CAPTIONS.water[0].zh} start={T.water + 0.5} />
      </Win>

      <Win t={t} a={T.village} b={T.quote2}>
        <Big3 lines={['HIDE FROM THE WIND.', 'SIT BY THE WATER.']} start={T.village + 0.1} size={76} top={250} accent="SIT BY THE WATER." />
        <Small3 text="THE SITE THE OLD TEXTS KEEP DESCRIBING" start={T.village + 1.0} top={420} />
        <Caption3 zh={CAPTIONS.village[0].zh} start={T.village + 0.5} />
      </Win>

      <Win t={t} a={T.quote2} b={T.name}>
        <Quote3 columns={['得水为上', '藏风次之']} start={T.quote2 + 0.2} top={300} size={84} />
        <Big3 lines={['WATER FIRST.', 'WIND SECOND.']} start={T.quote2 + 0.9} size={46} top={430} right={572} />
        <Small3 text={'《葬书》内篇\nBOOK OF BURIAL · INNER CHAPTER'} start={T.quote2 + 2.0} top={880} />
        <Caption3 zh={CAPTIONS.quote2[0].zh} start={T.quote2 + 0.5} />
      </Win>

      <Win t={t} a={T.name} b={T.qi}>
        <Big3 lines={['THE NAME IS', 'THE INSTRUCTION.']} start={T.name + 0.1} size={88} top={300} accent="THE INSTRUCTION." />
        <Seal3 chars="风水" start={stampT} top={640} left={760} size={140} />
        <Caption3 zh={CAPTIONS.name[0].zh} start={T.name + 0.6} />
      </Win>

      <Win t={t} a={T.qi} b={T.book}>
        <Big3 lines={['QI IS NOT AIR.']} start={T.qi + 0.1} size={112} top={272} accent="NOT AIR." />
        <Small3 text="IN THE TEXT THE CHARACTER ALSO MEANS BREATH, WEATHER, GROUND VAPOUR AND LIFE" start={T.qi + 0.9} top={440} size={20} />
        <Caption3 zh={CAPTIONS.qi[0].zh} start={T.qi + 0.4} />
      </Win>

      <Win t={t} a={T.book} b={T.limit}>
        <Big3 lines={['THE BOOK IS NOT', 'BY GUO PU.']} start={T.book + 0.1} size={84} top={262} accent="BY GUO PU." />
        <Small3 text={'THE RECEIVED TEXT IS USUALLY DATED TO THE SONG;\nTHE ATTRIBUTION TO GUO PU IS TRADITIONAL'} start={T.book + 0.9} top={450} size={20} />
        <Caption3 zh={CAPTIONS.book[0].zh} start={T.book + 0.4} />
      </Win>

      <Win t={t} a={T.limit} b={T.four}>
        <Big3 lines={['NOT EVERY RULE', 'CAN BE MEASURED.']} start={T.limit + 0.1} size={84} top={262} accent="CAN BE MEASURED." />
        <Small3 text="HOUSEHOLD RULES AND STAR CHARTS ARE OUT OF SCOPE" start={T.limit + 0.9} top={450} size={20} />
        <Caption3 zh={CAPTIONS.limit[0].zh} start={T.limit + 0.4} />
      </Win>

      <Win t={t} a={T.four} b={T.return}>
        <Big3 lines={['WIND. SUN.', 'WATER. SOIL.']} start={T.four + 0.1} size={86} top={250} />
        <div style={{position: 'absolute', left: 84, top: 470, display: 'flex', gap: 34}}>
          {[
            ['风', 'WIND'],
            ['日', 'SUN'],
            ['水', 'WATER'],
            ['土', 'SOIL'],
          ].map(([zh, en], i) => {
            const p = easeOut(clamp01((t - T.four - 0.9 - i * 0.16) / 0.6));
            return (
              <div key={en} style={{opacity: p, width: 180}}>
                <div style={{height: 1, width: 140 * p, background: T3.gold, opacity: 0.5}} />
                <div style={{fontFamily: '"STKaiti", "KaiTi", serif', fontSize: 44, color: T3.paper, marginTop: 8}}>{zh}</div>
                <div style={{fontFamily: DISPLAY, fontSize: 16, letterSpacing: '0.22em', color: T3.muted, marginTop: 6}}>{en}</div>
              </div>
            );
          })}
        </div>
        <Caption3 zh={CAPTIONS.four[0].zh} start={T.four + 0.5} />
      </Win>

      <Win t={t} a={T.return} b={T.question2}>
        <Big3 lines={['TAKE AWAY', 'THE MYSTERY.']} start={T.return + 0.1} size={84} top={250} />
        <Big3 lines={['THE LAND REMAINS.']} start={T.return + 5.2} size={84} top={470} accent="REMAINS." />
        <Caption3 zh={CAPTIONS.return[0].zh} start={T.return + 0.5} end={T.return + 5.0} />
        <Caption3 zh={CAPTIONS.return[1].zh} start={T.return + 5.4} />
      </Win>

      <Win t={t} a={T.question2} b={T.end}>
        <Big3 lines={['IT WAS A QUESTION', 'ABOUT THE GROUND.']} start={T.question2 + 0.1} size={82} top={262} accent="THE GROUND." />
        <Caption3 zh={CAPTIONS.question2[0].zh} start={T.question2 + 0.5} />
      </Win>

      <Win t={t} a={T.end} b={153}>
        <EndCard3 t={t} start={T.end} />
      </Win>

      {t < T.end && (
        <>
          <div style={{position: 'absolute', left: 84, top: 74, fontFamily: DISPLAY, fontSize: 18, letterSpacing: '0.26em', color: T3.faint}}>
            {String(Math.max(1, bar)).padStart(2, '0')} / 80
          </div>
          <div
            style={{
              position: 'absolute',
              right: 84,
              top: 74,
              fontFamily: DISPLAY,
              fontSize: 18,
              letterSpacing: '0.2em',
              color: T3.faint,
              textAlign: 'right',
            }}
          >
            {SERIES_EN}
          </div>
          <div style={{position: 'absolute', left: 84, right: 84, top: 118, height: 1, background: T3.paper, opacity: 0.14}} />
          <div style={{position: 'absolute', left: 84, right: 84, top: 1856, height: 1, background: T3.paper, opacity: 0.12}}>
            <div style={{width: `${(t / 152) * 100}%`, height: 2, background: T3.gold, opacity: 0.7}} />
          </div>
        </>
      )}
    </AbsoluteFill>
  );
};

export {lerp};
