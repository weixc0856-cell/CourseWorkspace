import React from 'react';
import {AbsoluteFill, Audio, Img, staticFile, useCurrentFrame} from 'remotion';
import {BPM, DISPLAY, FPS, P, SANS, clamp01, easeOut, lerp} from './theme';
import {CAPTIONS, EPISODE_EN, EPISODE_ZH, SERIES_EN, SERIES_ZH, T} from './data';
import {Landscape, Village, WindPaper} from './components/Landscape';
import {SimPanel} from './components/Inset';
import {Big, Meta, Quote, Rule, Seal, Small, ZhCaption} from './components/Type';

const Win: React.FC<{t: number; a: number; b: number; children: React.ReactNode}> = ({t, a, b, children}) => {
  if (t < a || t >= b) return null;
  const o = Math.min(1, (t - a) / 0.22) * Math.min(1, (b - t) / 0.2);
  return <div style={{position: 'absolute', inset: 0, opacity: o}}>{children}</div>;
};

const KAI = '"STKaiti", "KaiTi", "Adobe Kaiti Std", serif';

const Paper: React.FC<{t: number}> = ({t}) => {
  const tx = Math.sin(t * 0.11) * 7 + Math.sin(t * 0.037) * 5;
  const ty = Math.cos(t * 0.083) * 6 + Math.sin(t * 0.021) * 4;
  return (
    <AbsoluteFill style={{backgroundColor: P.paper}}>
      <div
        style={{
          position: 'absolute',
          inset: -40,
          backgroundImage: `url(${staticFile('fengshui/paper.png')})`,
          backgroundRepeat: 'repeat',
          backgroundSize: '512px 512px',
          opacity: 0.85,
          transform: `translate(${tx}px, ${ty}px)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(76% 60% at ${50 + Math.sin(t * 0.05) * 4}% ${42 + Math.cos(t * 0.04) * 3}%, rgba(245,240,230,0) 40%, rgba(191,182,162,0.3) 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};

const Chrome: React.FC<{t: number; bar: number}> = ({t, bar}) => (
  <>
    <div
      style={{
        position: 'absolute',
        left: 84,
        top: 74,
        fontFamily: DISPLAY,
        fontWeight: 400,
        fontSize: 18,
        letterSpacing: '0.26em',
        color: P.inkFaint,
      }}
    >
      {String(Math.max(1, bar)).padStart(2, '0')} / 80
    </div>
    <div
      style={{
        position: 'absolute',
        right: 84,
        top: 74,
        fontFamily: DISPLAY,
        fontWeight: 400,
        fontSize: 18,
        letterSpacing: '0.2em',
        color: P.inkFaint,
        textAlign: 'right',
      }}
    >
      {SERIES_EN}
    </div>
    <div style={{position: 'absolute', left: 84, right: 84, top: 118, height: 1, background: P.ink, opacity: 0.12}} />
    <div style={{position: 'absolute', left: 84, right: 84, top: 1856, height: 1, background: P.ink, opacity: 0.1}}>
      <div style={{width: `${(t / 152) * 100}%`, height: 2, background: P.cinnabar, opacity: 0.55}} />
    </div>
  </>
);

const FourLabels: React.FC<{t: number; start: number}> = ({t, start}) => {
  const items = [
    {x: 120, zh: '风', en: 'WIND'},
    {x: 340, zh: '日', en: 'SUN'},
    {x: 560, zh: '水', en: 'WATER'},
    {x: 780, zh: '土', en: 'SOIL'},
  ];
  return (
    <>
      {items.map((it, i) => {
        const p = easeOut(clamp01((t - start - i * 0.14) / 0.6));
        if (p <= 0) return null;
        return (
          <div key={i} style={{position: 'absolute', left: it.x, top: 1176, width: 200, opacity: p}}>
            <div style={{height: 1, background: P.ink, opacity: 0.35, width: 160 * p}} />
            <div style={{fontFamily: KAI, fontSize: 46, color: P.ink, marginTop: 10, lineHeight: 1}}>{it.zh}</div>
            <div
              style={{
                fontFamily: DISPLAY,
                fontSize: 18,
                letterSpacing: '0.24em',
                color: P.inkSoft,
                marginTop: 8,
              }}
            >
              {it.en}
            </div>
          </div>
        );
      })}
    </>
  );
};

const HookChars: React.FC<{t: number; start: number}> = ({t, start}) => {
  const chars = [
    {ch: '风', x: 168, d: 0},
    {ch: '水', x: 592, d: 0.75},
  ];
  return (
    <>
      {chars.map((c, i) => {
        const p = easeOut(clamp01((t - start - c.d) / 1.1));
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: c.x,
              top: 300,
              width: 320,
              height: 360,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                fontFamily: KAI,
                fontSize: 300,
                lineHeight: 1.1,
                color: P.ink,
                transform: `translateY(${(1 - p) * 26}%)`,
                opacity: p,
                clipPath: `inset(${(1 - p) * 100}% 0 0 0)`,
              }}
            >
              {c.ch}
            </div>
          </div>
        );
      })}
      <div
        style={{
          position: 'absolute',
          left: 536,
          top: 330,
          width: 1,
          height: 300 * easeOut(clamp01((t - start - 1.4) / 0.8)),
          background: P.ink,
          opacity: 0.25,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 168,
          top: 690,
          fontFamily: DISPLAY,
          fontSize: 26,
          letterSpacing: '0.34em',
          color: P.inkSoft,
          opacity: easeOut(clamp01((t - start - 1.9) / 0.8)),
        }}
      >
        WIND · WATER
      </div>
    </>
  );
};

const EndCard: React.FC<{t: number; start: number}> = ({t, start}) => {
  const p = easeOut(clamp01((t - start) / 1.0));
  if (p <= 0) return null;
  const drift = clamp01((t - start) / (152 - start));
  return (
    <>
      <AbsoluteFill style={{background: P.paper, opacity: 0.9 * p}} />
      <div
        style={{
          position: 'absolute',
          left: 84,
          top: 470,
          opacity: p,
          transform: `scale(${1.035 - 0.045 * easeOut(drift)}) translateY(${-10 * drift}px)`,
          transformOrigin: '20% 40%',
        }}
      >
        <div style={{fontFamily: DISPLAY, fontSize: 20, letterSpacing: '0.3em', color: P.inkSoft}}>EP 01</div>
        <div style={{height: 26}} />
        <div
          style={{
            fontFamily: DISPLAY,
            fontWeight: 900,
            fontSize: 92,
            lineHeight: 0.94,
            letterSpacing: '-0.03em',
            color: P.ink,
          }}
        >
          WHY IT IS
          <br />
          CALLED
          <br />
          <span style={{color: P.cinnabar}}>WIND-WATER</span>
        </div>
        <div style={{height: 40}} />
        <div style={{fontFamily: DISPLAY, fontSize: 19, letterSpacing: '0.22em', color: P.inkSoft, lineHeight: 1.7}}>
          {SERIES_EN}
          <br />
          EPISODE ONE OF EIGHT
        </div>
        <div style={{height: 26}} />
        <div style={{fontFamily: KAI, fontSize: 40, color: P.ink, lineHeight: 1.3}}>{SERIES_ZH}</div>
        <div style={{height: 8}} />
        <div style={{fontFamily: SANS, fontSize: 24, color: P.inkSoft, letterSpacing: '0.04em'}}>{EPISODE_ZH}</div>
      </div>
      <Seal chars="风水" start={start + 1.4} top={1290} left={760} size={150} />
      <div
        style={{
          position: 'absolute',
          left: 84,
          right: 84,
          bottom: 96,
          fontFamily: DISPLAY,
          fontSize: 16,
          letterSpacing: '0.16em',
          color: P.inkFaint,
          lineHeight: 1.8,
          opacity: p,
        }}
      >
        <span style={{fontFamily: KAI, fontSize: 19, letterSpacing: '0.06em'}}>《葬书》内篇 · 旧题晋郭璞</span>
        <br />
        FLOW FIELD: 2D SIMULATION, SCHEMATIC
        <br />
        MUSIC: GUZHENG MORNING — ANTTI LUODE, CC BY 3.0
      </div>
    </>
  );
};

export const FengShui: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const bar = Math.floor((t * BPM) / 240) + 1;

  // camera: slow push, then a pull-back that reveals the whole scroll
  const camScale =
    t < T.ridge
      ? lerp(1.0, 1.03, easeOut(clamp01(t / T.ridge)))
      : t < T.water
      ? lerp(1.03, 1.07, easeOut(clamp01((t - T.ridge) / (T.water - T.ridge))))
      : t < T.return
      ? lerp(1.05, 1.02, easeOut(clamp01((t - T.water) / (T.return - T.water))))
      : lerp(1.04, 1.0, easeOut(clamp01((t - T.return) / (T.end - T.return))));
  const camY = t < T.ridge ? lerp(0, -18, easeOut(clamp01(t / T.ridge))) : Math.sin((t - T.qi) * 0.18) * 9;

  const draw = easeOut(clamp01((t - (T.ridge - 0.4)) / 3.2));
  const riverDraw = easeOut(clamp01((t - (T.water - 0.6)) / 2.6));
  const windOpacity = Math.min(
    clamp01((t - (T.ridge + 0.6)) / 1.4),
    clamp01((T.village + 3.5 - t) / 2.0),
    1 - clamp01((t - (T.water - 1.2)) / 2.2)
  );

  return (
    <AbsoluteFill style={{backgroundColor: P.paper}}>
      <Audio src={staticFile('fengshui/wind-water-126.m4a')} />
      <Paper t={t} />

      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `scale(${camScale * (1.004 + 0.0035 * Math.sin(t * 0.14))}) translateY(${camY}px)`,
          transformOrigin: '50% 80%',
        }}
      >
        <Landscape t={t} draw={draw} farDraw={easeOut(clamp01(t / 3.2))} riverDraw={riverDraw} strata={1} />
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
          <WindPaper t={t} opacity={windOpacity * 0.9} />
          <Village p={easeOut(clamp01((t - (T.village - 0.3)) / 1.2)) * (t > T.return - 4 ? 1 : 1)} />
        </svg>
      </div>

      {/* I hook */}
      <Win t={t} a={T.hook} b={T.question}>
        <HookChars t={t} start={0.25} />
        <ZhCaption zh={CAPTIONS.hook[0].zh} start={2.2} />
      </Win>

      {/* II question */}
      <Win t={t} a={T.question} b={T.earlier}>
        <Big lines={['WHERE DOES THE', 'WORD COME FROM?']} start={T.question + 0.15} size={88} top={262} accent="WORD COME FROM?" />
        <Small
          text="EARLIEST EXTANT USE: A BURIAL MANUAL"
          start={T.question + 1.1}
          top={520}
        />
        <ZhCaption zh={CAPTIONS.question[0].zh} start={T.question + 0.5} />
      </Win>

      {/* III earlier practice */}
      <Win t={t} a={T.earlier} b={T.quote}>
        <Big lines={['BEFORE THE WORD,', 'THE PRACTICE.']} start={T.earlier + 0.1} size={84} top={262} accent="THE PRACTICE." />
        <div
          style={{
            position: 'absolute',
            left: 84,
            top: 520,
            fontFamily: KAI,
            fontSize: 46,
            color: P.ink,
            opacity: 0.9,
          }}
        >
          《诗经·大雅·公刘》 相其阴阳，观其流泉
        </div>
        <Small text="SHI JING · GONG LIU · WESTERN ZHOU" start={T.earlier + 1.2} top={600} />
        <ZhCaption zh={CAPTIONS.earlier[0].zh} start={T.earlier + 0.6} />
      </Win>

      {/* IV the quote */}
      <Win t={t} a={T.quote} b={T.ridge}>
        <Quote columns={['气乘风则散', '界水则止']} start={T.quote + 0.2} top={300} size={92} />
        <Big
          lines={['QI SCATTERS', 'IN WIND.', 'IT STOPS', 'AT WATER.']}
          start={T.quote + 0.8}
          size={54}
          top={430}
          right={604}
          lineHeight={1.02}
        />
        <Meta
          text={'《葬书》内篇\n旧题晋郭璞 (276–324)\nBOOK OF BURIAL · INNER CHAPTER'}
          start={T.quote + 2.2}
          top={900}
          left={84}
          color={P.inkSoft}
        />
        <ZhCaption zh={CAPTIONS.quote[0].zh} start={T.quote + 0.6} />
      </Win>

      {/* V ridge + VI simulation + VII chart */}
      <Win t={t} a={T.ridge} b={T.sim}>
        <Big lines={['A RIDGE IS A WALL.']} start={T.ridge + 0.1} size={92} top={250} accent="WALL." />
        <Small text="ONE CROSS-SECTION, TWO DRAWINGS" start={T.ridge + 0.9} top={380} />
        <ZhCaption zh={CAPTIONS.ridge[0].zh} start={T.ridge + 0.5} />
      </Win>
      <Win t={t} a={T.sim} b={T.water}>
        <Big lines={['BEHIND IT,', 'THE WIND DROPS.']} start={T.sim + 0.1} size={58} top={168} accent="THE WIND DROPS." />
        <SimPanel start={T.sim} chartStart={T.chart} y={352} />
        <ZhCaption zh={CAPTIONS.sim[0].zh} start={T.sim + 0.3} end={T.chart} />
        <ZhCaption zh={CAPTIONS.chart[0].zh} start={T.chart + 0.2} />
      </Win>

      {/* VII water */}
      <Win t={t} a={T.water} b={T.village}>
        <Big lines={['WATER STOPS', 'WHAT WIND', 'SCATTERS.']} start={T.water + 0.1} size={80} top={250} accent="SCATTERS." />
        <ZhCaption zh={CAPTIONS.water[0].zh} start={T.water + 0.5} />
      </Win>

      {/* VIII village */}
      <Win t={t} a={T.village} b={T.quote2}>
        <Big lines={['HIDE FROM THE WIND.', 'SIT BY THE WATER.']} start={T.village + 0.1} size={76} top={250} accent="SIT BY THE WATER." />
        <Small text="THE SITE THE OLD TEXTS KEEP DESCRIBING" start={T.village + 1.0} top={420} />
        <ZhCaption zh={CAPTIONS.village[0].zh} start={T.village + 0.5} />
      </Win>

      {/* IX second quote */}
      <Win t={t} a={T.quote2} b={T.name}>
        <Quote columns={['得水为上', '藏风次之']} start={T.quote2 + 0.2} top={300} size={84} />
        <Big lines={['WATER FIRST.', 'WIND SECOND.']} start={T.quote2 + 0.9} size={46} top={440} right={572} lineHeight={1.04} />
        <Meta text={'《葬书》内篇\nBOOK OF BURIAL · INNER CHAPTER'} start={T.quote2 + 2.0} top={880} left={84} color={P.inkSoft} />
        <ZhCaption zh={CAPTIONS.quote2[0].zh} start={T.quote2 + 0.5} />
      </Win>

      {/* X the name */}
      <Win t={t} a={T.name} b={T.qi}>
        <Big lines={['THE NAME IS', 'THE INSTRUCTION.']} start={T.name + 0.1} size={88} top={300} accent="THE INSTRUCTION." />
        <Seal chars="风水" start={T.name + 1.5} top={640} left={760} size={140} />
        <ZhCaption zh={CAPTIONS.name[0].zh} start={T.name + 0.6} />
      </Win>

      {/* XI-XIII boundaries */}
      <Win t={t} a={T.qi} b={T.book}>
        <Big lines={['QI IS NOT AIR.']} start={T.qi + 0.1} size={112} top={272} accent="NOT AIR." />
        <Small
          text="IN THE TEXT THE CHARACTER ALSO MEANS BREATH, WEATHER, GROUND VAPOUR AND LIFE"
          start={T.qi + 0.9}
          top={440}
        />
        <ZhCaption zh={CAPTIONS.qi[0].zh} start={T.qi + 0.4} />
      </Win>
      <Win t={t} a={T.book} b={T.limit}>
        <Big lines={['THE BOOK IS NOT', 'BY GUO PU.']} start={T.book + 0.1} size={84} top={262} accent="BY GUO PU." />
        <Small
          text={'THE RECEIVED TEXT IS USUALLY DATED TO THE SONG;\nTHE ATTRIBUTION TO GUO PU IS TRADITIONAL'}
          start={T.book + 0.9}
          top={450}
        />
        <ZhCaption zh={CAPTIONS.book[0].zh} start={T.book + 0.4} />
      </Win>
      <Win t={t} a={T.limit} b={T.four}>
        <Big lines={['NOT EVERY RULE', 'CAN BE MEASURED.']} start={T.limit + 0.1} size={84} top={262} accent="CAN BE MEASURED." />
        <Small text="HOUSEHOLD RULES AND STAR CHARTS ARE OUT OF SCOPE" start={T.limit + 0.9} top={450} />
        <ZhCaption zh={CAPTIONS.limit[0].zh} start={T.limit + 0.4} />
      </Win>

      {/* XIV four measurable things */}
      <Win t={t} a={T.four} b={T.return}>
        <Big lines={['WIND. SUN.', 'WATER. SOIL.']} start={T.four + 0.1} size={86} top={250} />
        <FourLabels t={t} start={T.four + 0.7} />
        <ZhCaption zh={CAPTIONS.four[0].zh} start={T.four + 0.5} />
      </Win>

      {/* XV-XVI return */}
      <Win t={t} a={T.return} b={T.question2}>
        <Big lines={['TAKE AWAY', 'THE MYSTERY.']} start={T.return + 0.1} size={84} top={250} />
        <Big lines={['THE LAND REMAINS.']} start={T.return + 5.2} size={84} top={470} accent="REMAINS." />
        <ZhCaption zh={CAPTIONS.return[0].zh} start={T.return + 0.5} end={T.return + 5.0} />
        <ZhCaption zh={CAPTIONS.return[1].zh} start={T.return + 5.4} />
      </Win>

      <Win t={t} a={T.question2} b={T.end}>
        <Big lines={['IT WAS A QUESTION', 'ABOUT THE GROUND.']} start={T.question2 + 0.1} size={82} top={262} accent="THE GROUND." />
        <ZhCaption zh={CAPTIONS.question2[0].zh} start={T.question2 + 0.5} />
      </Win>

      <Win t={t} a={T.end} b={153}>
        <EndCard t={t} start={T.end} />
      </Win>

      {t < T.end && <Chrome t={t} bar={bar} />}
    </AbsoluteFill>
  );
};
