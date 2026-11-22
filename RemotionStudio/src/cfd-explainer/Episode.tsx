// CfdEpisode: the typography layer for the T1-01 CFD explainer animation.
//
// Consumes the sidecar JSONs written by ScientificFigures/cfd/visual/
// shot_render.py: per-frame pixel anchors with occlusion picks, measured
// feature values, colour-bar stops. Nothing here places a label by hand --
// every leader line ends at the projected anchor for the current frame, and
// a label whose feature is not the thing under that pixel fades out.
//
// Layout contract (BUILD-SPEC section 4):
//   headline 56-72 px, body cards 30-36, labels 24-28, source 18-22.
//   Bottom 150 px is reserved for subtitles: no text, colour bar or leader
//   box enters it. One orange focus (#E8733B) per frame: at most one callout
//   is flagged focus and the physics layer keeps the separation line orange.
import React, {useMemo} from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {Formula} from '../components/Formula';
import {DISPLAY_FAMILY, SANS_FAMILY} from './fonts';

export const BG = '#0e1218';
export const ORANGE = '#E8733B';
export const INK = '#DDE6EE';
export const MUTED = '#8FA0B3';
export const SUBTITLE_BAND = 150;
const W = 1920;
const H = 1080;
const RAMP = 10;

export type PickState = {actor: string | null; on_feature: boolean; depth_delta_m?: number | null};
export type SidecarFrame = {
  f: number;
  camera: {pos: number[]; focal: number[]; up: number[]; fov: number} | null;
  anchors: Record<string, [number, number]>;
  pick: Record<string, PickState>;
};
export type Callout = {
  anchor: string | null;
  text: string;
  from: number;
  to: number;
  side?: 'left' | 'right' | 'up' | 'down';
  focus?: boolean;
  size?: number;
  y?: number;
};
export type Shot = {
  shot: string;
  mode?: string;
  fps: number;
  n_frames: number;
  duration: number;
  cp_clim: [number, number] | null;
  cp_bar_stops: [number, [number, number, number]][] | null;
  slow_motion_factor: number | null;
  source_line: string;
  field_note?: string;
  headline: {text: string; from: number; to: number} | null;
  callouts: Callout[];
  frames: SidecarFrame[];
  formula?: {latex: string; from: number; to: number; caption?: string};
};
export type EpisodeProps = {shots: Shot[]};

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const windowOpacity = (f: number, from: number, to: number) =>
  clamp01((f - from) / RAMP) * clamp01((to - f) / RAMP);

const pad5 = (n: number) => String(n).padStart(5, '0');

const CpBar: React.FC<{shot: Shot}> = ({shot}) => {
  if (!shot.cp_clim || !shot.cp_bar_stops) return null;
  const [lo, hi] = shot.cp_clim;
  const stops = shot.cp_bar_stops;
  // gradient built from the same 21-sample RdBu_r table the VTK LUT uses
  const grad = stops
    .map(([v, [r, g, b]]) => `rgb(${r},${g},${b}) ${(((hi - v) / (hi - lo)) * 100).toFixed(1)}%`)
    .reverse()
    .join(', ');
  const barH = 340;
  const top = 190;
  return (
    <div style={{position: 'absolute', right: 64, top, width: 150}}>
      <div style={{fontFamily: DISPLAY_FAMILY, fontSize: 30, color: INK, marginBottom: 8}}>
        {'C'}<sub style={{fontSize: 20}}>p</sub>
      </div>
      <div style={{display: 'flex'}}>
        <div
          style={{
            width: 22,
            height: barH,
            background: `linear-gradient(to bottom, ${grad})`,
            border: '1px solid rgba(140,160,180,0.4)',
          }}
        />
        <div style={{position: 'relative', width: 110, height: barH, marginLeft: 6}}>
          {[hi, (hi + lo) / 2, lo].map((v, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                top: i === 1 ? barH / 2 - 11 : i === 0 ? -2 : barH - 20,
                fontSize: 22,
                color: MUTED,
                fontFamily: SANS_FAMILY,
                whiteSpace: 'nowrap',
              }}
            >
              {v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)}
            </div>
          ))}
        </div>
      </div>
      <div style={{fontSize: 20, color: MUTED, marginTop: 10, fontFamily: SANS_FAMILY}}>
        {'dimensionless'}
      </div>
    </div>
  );
};

const Label: React.FC<{c: Callout; u: number; v: number; dim: boolean}> = ({c, u, v, dim}) => {
  const side = c.side || 'right';
  const fs = c.size || 26;
  const boxW = Math.min(560, Math.max(240, c.text.length * fs * 0.62));
  const off = 240;
  let bx: number, by: number, ax: number, ay: number; // box x,y; leader attach
  if (side === 'right') {
    // keep clear of the Cp colour bar column (rightmost ~230 px)
    bx = Math.min(u + off, W - boxW - 270);
    by = Math.max(140, Math.min(v - 34, H - SUBTITLE_BAND - 120));
    ax = bx;
    ay = by + 34;
  } else if (side === 'left') {
    bx = Math.max(u - off - boxW, 30);
    by = Math.max(140, Math.min(v - 34, H - SUBTITLE_BAND - 120));
    ax = bx + boxW;
    ay = by + 34;
  } else if (side === 'up') {
    bx = Math.max(30, Math.min(u - boxW / 2, W - boxW - 30));
    // keep clear of the headline/field-note block (top ~170 px)
    by = Math.max(175, v - 190);
    ax = bx + boxW / 2;
    ay = by + 68;
  } else {
    bx = Math.max(30, Math.min(u - boxW / 2, W - boxW - 30));
    // keep clear of the source line row (~890 px)
    by = Math.min(v + 150, H - SUBTITLE_BAND - 170);
    ax = bx + boxW / 2;
    ay = by;
  }
  const color = c.focus ? ORANGE : '#B9C6D4';
  return (
    <>
      <svg
        width={W}
        height={H}
        style={{position: 'absolute', left: 0, top: 0, pointerEvents: 'none'}}
      >
        <line x1={ax} y1={ay} x2={u} y2={v} stroke={color} strokeWidth={2.5} opacity={0.85} />
        <circle cx={u} cy={v} r={7} fill={c.focus ? ORANGE : 'none'} stroke={color} strokeWidth={2.5} />
      </svg>
      <div
        style={{
          position: 'absolute',
          left: bx,
          top: by,
          width: boxW,
          padding: '12px 16px',
          background: 'rgba(14,18,24,0.82)',
          border: `1px solid ${c.focus ? 'rgba(232,115,59,0.55)' : 'rgba(140,160,180,0.35)'}`,
          borderRadius: 10,
          fontFamily: SANS_FAMILY,
          fontWeight: 600,
          fontSize: fs,
          lineHeight: 1.3,
          color: dim ? MUTED : INK,
          opacity: dim ? 0.35 : 1,
        }}
      >
        {c.text}
      </div>
    </>
  );
};

export const Episode: React.FC<EpisodeProps> = ({shots}) => {
  const frame = useCurrentFrame();
  const offsets = useMemo(() => {
    let acc = 0;
    return shots.map((s) => {
      const start = acc;
      acc += s.n_frames;
      return start;
    });
  }, [shots]);
  let k = shots.length - 1;
  for (let i = 0; i < shots.length; i++) {
    if (frame < offsets[i] + shots[i].n_frames) {
      k = i;
      break;
    }
  }
  const shot = shots[k];
  const local = Math.max(0, Math.min(shot.n_frames - 1, frame - offsets[k]));
  const fr: SidecarFrame | undefined = shot.frames[local];
  if (!shot || !fr) {
    // a missing frame must NOT render a silent black slab -- fail visibly
    throw new Error(`cfd-explainer: no frame data for shot ${shot?.shot} idx ${local}`);
  }
  const hOp = shot.headline ? windowOpacity(local, shot.headline.from, shot.headline.to) : 0;
  return (
    <AbsoluteFill style={{backgroundColor: BG}}>
      <Img
        src={staticFile(`${shot.shot}/frame_${pad5(local)}.png`)}
        style={{width: W, height: H, position: 'absolute', left: 0, top: 0}}
      />
      {shot.headline && hOp > 0.01 && (
        <div style={{position: 'absolute', left: 64, top: 48, maxWidth: 1500, opacity: hOp}}>
          <div
            style={{
              fontFamily: DISPLAY_FAMILY,
              fontWeight: 300,
              fontSize: 62,
              lineHeight: 1.08,
              letterSpacing: 0.5,
              color: INK,
              textShadow: '0 2px 18px rgba(0,0,0,0.85)',
            }}
          >
            {shot.headline.text}
          </div>
          <div
            style={{
              marginTop: 10,
              fontFamily: SANS_FAMILY,
              fontSize: 22,
              color: MUTED,
              maxWidth: 1200,
              textShadow: '0 1px 10px rgba(0,0,0,0.9)',
            }}
          >
            {shot.slow_motion_factor
              ? `mean-field pathlines · steady RANS · slow motion ×${shot.slow_motion_factor}`
              : shot.field_note ?? 'steady RANS mean field'}
          </div>
        </div>
      )}
      {shot.formula && clamp01((local - shot.formula.from) / RAMP) * clamp01((shot.formula.to - local) / RAMP) > 0.01 && (
        <div
          style={{
            position: 'absolute',
            left: 64,
            top: 300,
            width: 760,
            padding: '26px 30px',
            background: 'rgba(14,18,24,0.80)',
            border: '1px solid rgba(140,160,180,0.35)',
            borderRadius: 14,
            opacity: clamp01((local - shot.formula.from) / RAMP) * clamp01((shot.formula.to - local) / RAMP),
          }}
        >
          <Formula latex={shot.formula.latex} fontSize={46} align="left" />
          {shot.formula.caption && (
            <div style={{fontFamily: SANS_FAMILY, fontSize: 26, color: MUTED, marginTop: 14}}>
              {shot.formula.caption}
            </div>
          )}
        </div>
      )}
      {shot.callouts.map((c, i) => {
        const op = windowOpacity(local, c.from, c.to);
        if (op <= 0.01) return null;
        if (!c.anchor) {
          // anchorless card: fixed panel, kept above the subtitle band
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: 64,
                top: c.y ?? 220,
                maxWidth: 900,
                padding: '14px 18px',
                background: 'rgba(14,18,24,0.80)',
                border: `1px solid ${c.focus ? 'rgba(232,115,59,0.55)' : 'rgba(140,160,180,0.35)'}`,
                borderRadius: 10,
                fontFamily: SANS_FAMILY,
                fontWeight: 600,
                fontSize: c.size || 32,
                lineHeight: 1.35,
                color: INK,
                opacity: op,
              }}
            >
              {c.text}
            </div>
          );
        }
        const px = fr.anchors[c.anchor];
        const pick = fr.pick[c.anchor];
        if (!px) return null;
        if (!pick || !pick.on_feature) return null; // occluded: label leaves, not dims
        return (
          <div key={i} style={{opacity: op}}>
            <Label c={c} u={px[0]} v={px[1]} dim={false} />
          </div>
        );
      })}
      <CpBar shot={shot} />
      <div
        style={{
          position: 'absolute',
          left: 64,
          top: H - SUBTITLE_BAND - 40,
          fontFamily: SANS_FAMILY,
          fontSize: 20,
          color: MUTED,
          maxWidth: 1792 - 128,
          opacity: 0.95,
          textShadow: '0 1px 10px rgba(0,0,0,0.9)',
        }}
      >
        {shot.source_line}
      </div>
    </AbsoluteFill>
  );
};
