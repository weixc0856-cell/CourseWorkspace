import React from 'react';
import {Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT, ease} from '../chapter/theme';

// Evidence stays evidence: the original scan keeps every pixel. It sits on a
// warm paper panel (padding, border, shadow) and the explanation is an overlay
// in image coordinates: a spotlight, a mask that reveals along an existing
// line, or a label pointing at a point on the figure.
export type FigureOverlay =
  | {kind: 'spotlight'; x: number; y: number; w: number; h: number; at?: number}
  | {kind: 'reveal'; from: number; to: number; at?: number}
  | {kind: 'label'; x: number; y: number; pointX: number; pointY: number; text: string; at?: number};

export type AnnotatedFigureProps = {
  image: string;
  imageWidth: number;
  imageHeight: number;
  eyebrow?: string;
  title?: string;
  source?: string;
  overlays?: FigureOverlay[];
  duration?: number;
};

const BOX = {w: 1668, h: 580};

export const AnnotatedFigure: React.FC<AnnotatedFigureProps> = ({
  image,
  imageWidth,
  imageHeight,
  eyebrow = 'T1-01 · 02 / WHERE DRAG LIVES',
  title = 'Pressure, not paint',
  source = 'Original source figure',
  overlays = [],
  duration = 5,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const appear = ease(t / 0.7);
  const scale = Math.min(BOX.w / imageWidth, BOX.h / imageHeight);
  const rect = {
    w: imageWidth * scale,
    h: imageHeight * scale,
    x: (BOX.w - imageWidth * scale) / 2,
    y: (BOX.h - imageHeight * scale) / 2,
  };
  const panel = {left: 96, top: 270, width: 1728, height: 640, pad: 30};
  return (
    <SceneFrame
      style={{
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        {eyebrow}
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, fontFamily: DISPLAY, fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper, opacity: appear}}>
        {title}
      </div>

      {/* paper panel: the scan itself is never filtered, tinted or inverted */}
      <div
        style={{
          position: 'absolute',
          left: panel.left,
          top: panel.top,
          width: panel.width,
          height: panel.height,
          background: '#EDE7DA',
          border: '1px solid rgba(27,30,35,0.22)',
          boxShadow: '0 30px 90px rgba(0,0,0,0.55)',
          opacity: appear,
        }}
      >
        <Img
          src={staticFile(image)}
          style={{
            position: 'absolute',
            left: panel.pad + rect.x,
            top: panel.pad + rect.y,
            width: rect.w,
            height: rect.h,
          }}
        />
        <svg
          width={rect.w}
          height={rect.h}
          viewBox={`0 0 ${imageWidth} ${imageHeight}`}
          style={{position: 'absolute', left: panel.pad + rect.x, top: panel.pad + rect.y, overflow: 'visible'}}
        >
          <defs>
            <clipPath id="reveal">
              <rect x={0} y={0} width={imageWidth} height={imageHeight} />
            </clipPath>
            <mask id="spot">
              <rect x={0} y={0} width={imageWidth} height={imageHeight} fill="white" />
              {overlays
                .filter((o): o is Extract<FigureOverlay, {kind: 'spotlight'}> => o.kind === 'spotlight')
                .map((o, i) => {
                  const on = ease((t - (o.at ?? 0.6)) / 0.6);
                  return <rect key={i} x={o.x} y={o.y} width={o.w} height={o.h} fill="black" opacity={on} rx={6} />;
                })}
            </mask>
          </defs>
          <rect
            x={0}
            y={0}
            width={imageWidth}
            height={imageHeight}
            fill="rgba(5,7,10,0.30)"
            mask="url(#spot)"
            opacity={Math.max(0, ...overlays.map((o) => (o.kind === 'spotlight' ? ease((t - (o.at ?? 0.6)) / 0.6) : 0)))}
          />
          {overlays
            .filter((o): o is Extract<FigureOverlay, {kind: 'spotlight'}> => o.kind === 'spotlight')
            .map((o, i) => {
              const on = ease((t - (o.at ?? 0.6)) / 0.6);
              return (
                <rect
                  key={`edge-${i}`}
                  x={o.x}
                  y={o.y}
                  width={o.w}
                  height={o.h}
                  fill="none"
                  stroke={C.orange}
                  strokeWidth={4}
                  opacity={on}
                  rx={6}
                />
              );
            })}
          {overlays
            .filter((o): o is Extract<FigureOverlay, {kind: 'reveal'}> => o.kind === 'reveal')
            .map((o, i) => {
              const on = ease((t - (o.at ?? 1.2)) / 1.2);
              const x = o.from + (o.to - o.from) * on;
              return (
                <line
                  key={`reveal-${i}`}
                  x1={x}
                  y1={0}
                  x2={x}
                  y2={imageHeight}
                  stroke={C.orange}
                  strokeWidth={3}
                  opacity={0.85}
                />
              );
            })}
          {overlays
            .filter((o): o is Extract<FigureOverlay, {kind: 'label'}> => o.kind === 'label')
            .map((o, i) => {
              const on = ease((t - (o.at ?? 2.0)) / 0.6);
              return (
                <g key={`label-${i}`} opacity={on}>
                  <line x1={o.x} y1={o.y} x2={o.pointX} y2={o.pointY} stroke={C.orange} strokeWidth={2} />
                  <circle cx={o.pointX} cy={o.pointY} r={6} fill={C.orange} />
                  <text x={o.x} y={o.y - 8} fill="#7A2E12" fontSize={17} fontFamily={FONT}>
                    {o.text}
                  </text>
                </g>
              );
            })}
        </svg>
      </div>

      <div style={{position: 'absolute', left: 96, right: 96, bottom: 130, display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.38)', fontSize: 15, letterSpacing: '0.12em'}}>
        <span>{source}</span>
        <span>ORIGINAL FIGURE · UNTOUCHED</span>
      </div>
    </SceneFrame>
  );
};
