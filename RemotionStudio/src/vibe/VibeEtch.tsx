import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {SHOTS, Shot} from './data';
import {C, DISPLAY, FPS, SANS, beatPulse, clamp01, easeOut} from './theme';
import {Caption, ChapterTag, Giant, Kicker, Note, TopHud} from './components/Type';
import {Profile, SCENES, depthNm, getFrame} from './components/Profile';
import {Ions} from './components/Ions';
import {
  Backdrop,
  BeatVignette,
  CutFlash,
  Grain,
  ProgressLine,
  Scanlines,
  Timecode,
  Vignette,
} from './components/Overlays';
import {
  Callout,
  CalloutLayer,
  ChipMacro,
  DeepTrench,
  DepthGauge,
  GasPulse,
  HookVisual,
  MetricBar,
  PanelLabel,
  ScaleVisual,
} from './components/Visuals';

const S = Object.fromEntries(SHOTS.map((s) => [s.id, s])) as Record<string, Shot>;

const useShot = (id: string) => {
  const s = S[id];
  const frame = useCurrentFrame();
  const d = s.to - s.from;
  return {s, frame, p: Math.min(1, frame / Math.max(1, d - 1)), t: frame / FPS, d};
};

const Shot: React.FC<{id: string; children: React.ReactNode}> = ({id, children}) => {
  const s = S[id];
  return (
    <Sequence from={s.from} durationInFrames={s.to - s.from} name={id}>
      {children}
    </Sequence>
  );
};

const Panel: React.FC<React.CSSProperties & {children: React.ReactNode}> = ({children, ...st}) => (
  <div style={{position: 'absolute', ...st}}>{children}</div>
);

const CROP = {
  iso: [100, 18, 160, 76],
  dir: [105, 18, 150, 132],
  loading: [55, 18, 250, 132],
  grass: [110, 55, 145, 100],
  notch: [110, 78, 140, 64],
  closeup: [130, 18, 100, 150],
};

// ---------------------------------------------------------------- 01 hook
const HookShot: React.FC = () => {
  const {s, p, t} = useShot('hook');
  return (
    <AbsoluteFill>
      <Backdrop accent={C.cyan} />
      <HookVisual progress={p} t={t} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 190}}>
        <Kicker text="PLASMA ETCH // 01" color={C.cyan} delay={3} />
        <div style={{height: 24}} />
        <Giant lines={['YOUR PHONE', 'IS A CITY']} size={112} delay={7} />
        <div style={{marginTop: 8}}>
          <Giant
            lines={['OF 20 BILLION', 'SWITCHES']}
            size={112}
            delay={16}
            color={C.body}
            accent="BILLION"
            accentColor={C.cyan}
          />
        </div>
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={18} />
      <CutFlash color={C.cyan} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 02 scale
const ScaleShot: React.FC = () => {
  const {s, p} = useShot('scale');
  return (
    <AbsoluteFill>
      <Backdrop accent={C.violet} />
      <ScaleVisual progress={p} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 190}}>
        <Kicker text="SCALE // 02" color={C.violet} delay={3} />
        <div style={{height: 24}} />
        <Giant lines={['3 NM', 'CLASS']} size={196} delay={6} accent="NM" accentColor={C.violet} />
        <div style={{marginTop: 18}}>
          <Note text="TENS OF THOUSANDS × THINNER THAN A HAIR" color={C.muted} />
        </div>
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={14} />
      <CutFlash color={C.violet} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 03 isotropic
const IsoShot: React.FC = () => {
  const {s, p, t} = useShot('iso');
  const fr = getFrame('isotropic', p);
  const under = Math.round((fr.stats.undercut ?? 0) * 8);
  return (
    <AbsoluteFill>
      <Backdrop accent={C.red} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 178}}>
        <Kicker text="ISOTROPIC ETCH // 03" color={C.red} delay={3} />
        <div style={{height: 20}} />
        <Giant lines={['WET ETCH', 'EATS SIDEWAYS']} size={92} delay={6} accent="SIDEWAYS" accentColor={C.red} />
      </div>
      <Panel left={110} right={110} top={800} height={440}>
        <Profile id="isotropic" progress={p} viewBox={CROP.iso} accent={C.red} showLabels={false}>
          <Ions
            sceneId="isotropic"
            progress={p}
            t={t}
            mode="chem"
            color={C.red}
            count={80}
            intensity={0.85}
            viewBox={CROP.iso}
          />
          <CalloutLayer viewBox={CROP.iso}>
            <PanelLabel x={104} y={26} text="ISOTROPIC WET ETCH" color={C.red} size={4.8} />
            {p > 0.35 && (
              <Callout x={124} y={52} dx={40} dy={12} text="UNDERCUT" color={C.red} progress={p} delay={0.35} size={5.2} boxW={42} />
            )}
            {p > 0.6 && (
              <Callout x={216} y={52} dx={-40} dy={12} text="UNDERCUT" color={C.red} progress={p} delay={0.6} size={5.2} boxW={42} />
            )}
          </CalloutLayer>
        </Profile>
      </Panel>
      <div style={{position: 'absolute', left: 96, right: 96, top: 1290, display: 'flex', gap: 46}}>
        <MetricBar label="SIDEWALL CUT" value={under} max={280} color={C.red} width={400} />
        <MetricBar label="DEPTH" value={depthNm(fr.stats.depth)} max={420} color={C.cyan} width={400} />
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={10} />
      <CutFlash color={C.red} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 04 breakdown
const BreakdownShot: React.FC = () => {
  const {s, p, t} = useShot('breakdown');
  const pulse = 0.55 + 0.45 * beatPulse(t, 6);
  return (
    <AbsoluteFill>
      <Backdrop accent={C.violet} />
      <div style={{position: 'absolute', left: 110, right: 110, top: 700, height: 600, opacity: 0.22}}>
        <Profile id="isotropic" progress={1} viewBox={CROP.iso} accent={C.violet} showLabels={false} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 536,
          top: 610,
          width: 8,
          height: 760,
          background: `linear-gradient(to bottom, ${C.violet}00, ${C.violet}CC, ${C.cyan}00)`,
          filter: 'blur(2px)',
          opacity: pulse,
          boxShadow: `0 0 60px ${C.violet}`,
        }}
      />
      <div style={{position: 'absolute', left: 80, right: 80, top: 340, textAlign: 'center'}}>
        <Kicker text="THE SECOND INGREDIENT" color={C.violet} delay={4} align="center" />
        <div style={{height: 26}} />
        <Giant lines={['ADD', 'IONS']} size={210} delay={8} align="center" accent="IONS" accentColor={C.violet} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 80,
          right: 80,
          top: 1370,
          display: 'flex',
          justifyContent: 'center',
          gap: 18,
          opacity: clamp01((p - 0.2) / 0.3),
        }}
      >
        <Note text="DIRECTIONAL" color={C.cyan} />
        <Note text="·" color={C.faint} />
        <Note text="VIOLENT" color={C.cyan} />
        <Note text="·" color={C.faint} />
        <Note text="PRECISE" color={C.cyan} />
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={12} />
      <CutFlash color={C.violet} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 05 directional
const DirectionalShot: React.FC = () => {
  const {s, p, t} = useShot('directional');
  const fr = getFrame('directional', p);
  return (
    <AbsoluteFill>
      <Backdrop accent={C.cyan} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 178}}>
        <Kicker text="PASSIVATION // 05" color={C.cyan} delay={3} />
        <div style={{height: 20}} />
        <Giant lines={['PROTECT', 'THE WALLS']} size={96} delay={6} accent="WALLS" accentColor={C.pink} />
        <div style={{marginTop: 6}}>
          <Giant lines={['ETCH THE FLOOR']} size={96} delay={14} color={C.body} accent="FLOOR" accentColor={C.cyan} />
        </div>
      </div>
      <Panel left={110} right={110} top={690} height={600}>
        <Profile id="directional" progress={p} viewBox={CROP.dir} accent={C.cyan} showLabels={false}>
          <Ions
            sceneId="directional"
            progress={p}
            t={t}
            mode="ion"
            color={C.cyan}
            count={110}
            intensity={1}
            viewBox={CROP.dir}
          />
          <CalloutLayer viewBox={CROP.dir}>
            <PanelLabel x={108} y={26} text="ION FLUX · VERTICAL" color={C.cyan} size={5.2} />
            {p > 0.45 && (
              <Callout x={148} y={92} dx={-30} dy={-24} text="C4F8 POLYMER" color={C.pink} progress={p} delay={0.45} size={5.4} boxW={48} />
            )}
            {p > 0.55 && (
              <Callout x={196} y={120} dx={8} dy={18} text="SIDEWALL PROTECTED" color={C.pink} progress={p} delay={0.55} size={4.8} boxW={60} />
            )}
          </CalloutLayer>
        </Profile>
      </Panel>
      <DepthGauge cells={fr.stats.depth} color={C.cyan} label="ETCH DEPTH" bottom={560} />
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={10} />
      <CutFlash color={C.cyan} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 06 bosch
const BoschShot: React.FC = () => {
  const {s, p, t} = useShot('bosch');
  const fr = getFrame('bosch_closeup', p);
  const gasPhase = Math.floor(t / 1.875) % 2;
  const zoom = 1 + 0.2 * easeOut((p - 0.45) / 0.55);
  return (
    <AbsoluteFill>
      <Backdrop accent={C.pink} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 168}}>
        <Kicker text="BOSCH PROCESS // 06" color={C.pink} delay={3} />
        <div style={{height: 20}} />
        <Giant lines={['ETCH.', 'DEPOSIT.']} size={100} delay={6} accent="DEPOSIT." accentColor={C.pink} />
        <Giant lines={['REPEAT.']} size={100} delay={16} />
      </div>
      <div style={{position: 'absolute', left: 80, right: 80, top: 545}}>
        <GasPulse t={t} color={C.cyan} />
      </div>
      <Panel left={260} right={260} top={620} height={800}>
        <Profile
          id="bosch_closeup"
          progress={p}
          viewBox={CROP.closeup}
          accent={C.pink}
          showLabels={false}
          showPassiv={false}
          zoom={zoom}
        >
          <Ions
            sceneId="bosch_closeup"
            progress={p}
            t={t}
            mode="ion"
            color={C.cyan}
            count={35}
            intensity={gasPhase === 0 ? 1 : 0.12}
            viewBox={CROP.closeup}
          />
          <Ions
            sceneId="bosch_closeup"
            progress={p}
            t={t + 0.7}
            mode="polymer"
            color={C.pink}
            count={18}
            intensity={gasPhase === 1 ? 0.8 : 0.08}
            seed={29}
            viewBox={CROP.closeup}
          />
          <CalloutLayer viewBox={CROP.closeup}>
            <PanelLabel x={134} y={26} text="CLOSEUP · SCHEMATIC" color={C.pink} size={4.8} />
            {p > 0.3 && (
              <Callout x={140} y={78} dx={26} dy={-22} text="SCALLOP" color={C.pink} progress={p} delay={0.3} size={5.2} boxW={42} />
            )}
          </CalloutLayer>
        </Profile>
      </Panel>
      <div
        style={{
          position: 'absolute',
          left: 260,
          right: 260,
          top: 1435,
          display: 'flex',
          justifyContent: 'space-between',
          fontFamily: DISPLAY,
          fontWeight: 800,
          fontSize: 17,
          letterSpacing: '0.2em',
          color: C.muted,
        }}
      >
        <span>CYCLE {String(fr.stats.cycles ?? 0).padStart(2, '0')}</span>
        <span style={{color: C.pink}}>ONE BITE PER CYCLE</span>
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={10} />
      <CutFlash color={C.pink} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 07a loading
const LoadingShot: React.FC = () => {
  const {s, p} = useShot('loading');
  const fr = getFrame('loading', p);
  const depths = fr.stats.depths ?? [0, 0];
  return (
    <AbsoluteFill>
      <Backdrop accent={C.amber} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 180}}>
        <Kicker text="FAILURE 01 // MICRO-LOADING" color={C.amber} delay={3} />
        <div style={{height: 18}} />
        <Giant lines={['DENSE', 'STARVES']} size={120} delay={6} accent="STARVES" accentColor={C.amber} />
      </div>
      <Panel left={64} right={64} top={780} height={500}>
        <Profile id="loading" progress={p} viewBox={CROP.loading} accent={C.amber} showLabels={false}>
          <Ions
            sceneId="loading"
            progress={p}
            t={p * 9}
            mode="ion"
            color={C.cyan}
            count={80}
            intensity={0.85}
            viewBox={CROP.loading}
          />
          <CalloutLayer viewBox={CROP.loading}>
            <Callout x={122} y={44} dx={0} dy={14} text="WIDE" color={C.cyan} progress={p} delay={0.2} size={5.4} boxW={40} />
            <Callout x={239} y={44} dx={42} dy={16} text="NARROW" color={C.amber} progress={p} delay={0.35} size={5.2} boxW={46} />
          </CalloutLayer>
        </Profile>
      </Panel>
      <div style={{position: 'absolute', left: 96, right: 96, top: 1310, display: 'flex', gap: 60}}>
        <MetricBar label="WIDE TRENCH" value={depthNm(depths[0] ?? 0)} max={420} color={C.cyan} width={400} />
        <MetricBar label="NARROW TRENCH" value={depthNm(depths[1] ?? 0)} max={420} color={C.amber} width={400} />
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={8} />
      <CutFlash color={C.amber} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 07b grass
const GrassShot: React.FC = () => {
  const {s, p} = useShot('grass');
  const gp = 0.35 + 0.65 * p;
  const fr = getFrame('grass', gp);
  return (
    <AbsoluteFill>
      <Backdrop accent={C.amber} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 180}}>
        <Kicker text="FAILURE 02 // GRASS" color={C.amber} delay={3} />
        <div style={{height: 18}} />
        <Giant lines={['GRASS']} size={172} delay={6} accent="GRASS" accentColor={C.amber} />
      </div>
      <Panel left={110} right={110} top={750} height={600}>
        <Profile id="grass" progress={gp} viewBox={CROP.grass} accent={C.amber} showLabels={false}>
          <CalloutLayer viewBox={CROP.grass}>
            {gp > 0.45 && (
              <Callout x={160} y={120} dx={-10} dy={-14} text="MICROMASK" color={C.pink} progress={gp} delay={0.45} size={5.0} boxW={46} />
            )}
            {gp > 0.55 && (
              <Callout x={190} y={130} dx={30} dy={-14} text="PILLAR" color={C.amber} progress={gp} delay={0.55} size={5.2} boxW={40} />
            )}
          </CalloutLayer>
        </Profile>
      </Panel>
      <div style={{position: 'absolute', left: 96, right: 96, top: 1370}}>
        <MetricBar label="PILLAR ZONE" value={depthNm(fr.stats.depth)} max={420} color={C.amber} width={400} />
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={8} />
      <CutFlash color={C.amber} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 07c notch
const NotchShot: React.FC = () => {
  const {s, p} = useShot('notch');
  const np = 0.62 + 0.38 * p;
  return (
    <AbsoluteFill>
      <Backdrop accent={C.red} />
      <div style={{position: 'absolute', left: 80, right: 80, top: 170}}>
        <Kicker text="FAILURE 03 // NOTCHING" color={C.red} delay={3} />
        <div style={{height: 18}} />
        <Giant lines={['NOTCHING']} size={124} delay={6} accent="NOTCHING" accentColor={C.red} />
      </div>
      <Panel left={64} right={64} top={800} height={435}>
        <Profile id="notch" progress={np} viewBox={CROP.notch} accent={C.red} showLabels={false}>
          <CalloutLayer viewBox={CROP.notch}>
            <PanelLabel x={114} y={87} text="OXIDE INTERFACE" color={C.red} size={5.2} />
            {np > 0.5 && (
              <Callout x={180} y={127} dx={0} dy={-16} text="LATERAL ETCH" color={C.red} progress={np} delay={0.5} size={5.0} boxW={56} />
            )}
          </CalloutLayer>
        </Profile>
      </Panel>
      <div style={{position: 'absolute', left: 96, right: 96, top: 1280, display: 'flex', gap: 50}}>
        <MetricBar label="OVER-ETCH" value={100 + Math.round(p * 30)} max={140} color={C.red} suffix="%" width={360} />
        <MetricBar label="NOTCH" value={Math.round((getFrame('notch', np).stats.notch ?? 0) * 3)} max={140} color={C.amber} width={360} />
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={8} />
      <CutFlash color={C.red} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 08 payoff
const PayoffShot: React.FC = () => {
  const {s, p, t} = useShot('payoff');
  const macro = clamp01((p - 0.58) / 0.3);
  const layers = clamp01((p - 0.3) / 0.35);
  return (
    <AbsoluteFill>
      <Backdrop accent={C.cyan} />
      <DeepTrench progress={p} t={t} />
      <div style={{position: 'absolute', inset: 0, opacity: macro}}>
        <ChipMacro progress={macro} t={t} />
      </div>
      <div style={{position: 'absolute', left: 80, right: 80, top: 170}}>
        <Kicker text="HIGH-ASPECT-RATIO // 08" color={C.cyan} delay={3} />
        <div style={{height: 16}} />
        <Giant lines={['100:1']} size={196} delay={6} accent="100:1" accentColor={C.cyan} />
        <div style={{marginTop: 2}}>
          <Note text="ASPECT RATIO · SCHEMATIC" color={C.muted} />
        </div>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 80,
          right: 80,
          top: 610,
          opacity: layers,
        }}
      >
        <Giant lines={['200+ LAYERS']} size={64} delay={2} color={C.body} accent="LAYERS" accentColor={C.violet} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 80,
          right: 80,
          bottom: 520,
          opacity: macro,
          textAlign: 'center',
        }}
      >
        <div style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 58, letterSpacing: '0.02em', color: C.ink}}>
          ONE CHIP
        </div>
      </div>
      <ChapterTag chapter={s.chapter} kicker={s.kicker} color={s.accent} />
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={10} />
      <CutFlash color={C.cyan} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 09 end
const EndShot: React.FC = () => {
  const {s, frame, d, t} = useShot('end');
  const fade = interpolate(frame, [d - 8, d - 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#03050A'}}>
      <Backdrop accent={C.cyan} />
      <div style={{position: 'absolute', left: 90, right: 90, top: 420, textAlign: 'center'}}>
        <Kicker text="END // SIMULATION" color={C.cyan} delay={2} align="center" />
        <div style={{height: 30}} />
        <Giant
          lines={['EVERY CHIP', 'IS A', 'LANDSCAPE']}
          size={104}
          delay={2}
          align="center"
          accent="LANDSCAPE"
          accentColor={C.cyan}
        />
        <div
          style={{
            margin: '38px auto 0',
            width: 90,
            height: 2,
            background: C.cyan,
            opacity: 0.7,
            boxShadow: `0 0 18px ${C.cyan}`,
          }}
        />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 100,
          right: 100,
          top: 1380,
          textAlign: 'center',
          fontFamily: DISPLAY,
          fontWeight: 800,
          fontSize: 17,
          letterSpacing: '0.24em',
          color: C.faint,
          lineHeight: 1.8,
          textTransform: 'uppercase',
        }}
      >
        SIMULATION · QUALITATIVE TRENDS ONLY
        <br />
        NOT A REAL TOOL · NOT CALIBRATED
      </div>
      <Caption en={s.captionEn} zh={s.captionZh} accent={s.accent} delay={10} />
      <AbsoluteFill style={{background: '#000', opacity: fade}} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- root
export const VibeEtch: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const t = frame / FPS;
  return (
    <AbsoluteFill style={{backgroundColor: C.bg}}>
      <Audio src={staticFile('vibe/we-never.m4a')} />
      <Shot id="hook"><HookShot /></Shot>
      <Shot id="scale"><ScaleShot /></Shot>
      <Shot id="iso"><IsoShot /></Shot>
      <Shot id="breakdown"><BreakdownShot /></Shot>
      <Shot id="directional"><DirectionalShot /></Shot>
      <Shot id="bosch"><BoschShot /></Shot>
      <Shot id="loading"><LoadingShot /></Shot>
      <Shot id="grass"><GrassShot /></Shot>
      <Shot id="notch"><NotchShot /></Shot>
      <Shot id="payoff"><PayoffShot /></Shot>
      <Shot id="end"><EndShot /></Shot>

      <TopHud t={t} />
      <BeatVignette color={C.cyan} />
      <Grain />
      <Scanlines />
      <Vignette />
      <ProgressLine color={C.cyan} />
      <Timecode />
      <AbsoluteFill
        style={{
          background: 'linear-gradient(to top, rgba(5,7,12,0.9), rgba(5,7,12,0))',
          top: 'auto',
          height: 160,
          bottom: 0,
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
  );
};
