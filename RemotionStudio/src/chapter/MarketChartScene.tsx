import React from 'react';
import {SceneFrame} from './SceneFrame';
import {useSceneTime} from './timing';
import {C, DISPLAY, FONT, ease} from './theme';

export type MarketPoint = {
  label: string;
  value: number;
  note?: string;
};

export type MarketChartProps = {
  points?: MarketPoint[];
  title?: string;
  /** Required on purpose: a price chart with no source is a claim without provenance. */
  source?: string;
  note?: string;
  duration?: number;
};

// Four recorded closes/opens only. No daily series exists for this window, so
// nothing here interpolates: each marker is a real record, and the gaps between
// them are drawn as drops, never as a trend.
export const DEFAULT_POINTS: MarketPoint[] = [
  {label: 'OCT 6 CLOSE', value: 239.24, note: 'record close'},
  {label: 'NOV 12 OPEN', value: 151.0, note: '−13.1%'},
  {label: 'NOV 12 LOW', value: 148.8, note: 'intraday'},
  {label: 'NOV 12 CLOSE', value: 166.19, note: '−4.34%'},
];

export const MarketChartScene: React.FC<MarketChartProps> = ({
  points = DEFAULT_POINTS,
  title = 'Four recorded points. Not a daily series.',
  source,
  note = '4 recorded points · not a daily series',
  duration,
}) => {
  if (!source) {
    throw new Error('MarketChart requires a source: every price on screen must name where it came from');
  }
  const t = useSceneTime(duration);

  const box = {left: 96, top: 240, width: 1728, height: 520};
  // Keep the first and last markers clear of the 96 px safe margin once their labels are centred.
  const inset = 150;
  const values = points.map((p) => p.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = (hi - lo) * 0.18 || 1;
  const yMin = lo - pad;
  const yMax = hi + pad;

  const xAt = (i: number) =>
    box.left + inset + (points.length === 1 ? (box.width - 2 * inset) / 2 : ((box.width - 2 * inset) * i) / (points.length - 1));
  const yAt = (v: number) =>
    box.top + box.height - ((v - yMin) / (yMax - yMin)) * box.height;

  return (
    <SceneFrame
      style={{
        background: 'radial-gradient(110% 90% at 40% 40%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        MARKETS · DOCUMENTED
      </div>
      <div style={{position: 'absolute', left: 96, top: 136, opacity: ease(t / 0.8), fontFamily: DISPLAY, fontSize: 44, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper}}>
        {title}
      </div>

      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const y = box.top + box.height * f;
          return <line key={f} x1={box.left} x2={box.left + box.width} y1={y} y2={y} stroke="rgba(244,241,234,0.10)" strokeWidth={1} />;
        })}

        {points.map((p, i) => {
          const x = xAt(i);
          const y = yAt(p.value);
          const appear = ease((t - 0.9 - i * 0.85) / 0.55);
          const prevY = i === 0 ? y : yAt(points[i - 1].value);
          const drop = ease((t - 1.15 - i * 0.85) / 0.5);
          return (
            <g key={p.label} opacity={appear}>
              {i > 0 && (
                <g opacity={drop}>
                  <line x1={x} x2={x} y1={prevY} y2={y} stroke="rgba(122,216,232,0.55)" strokeWidth={2} strokeDasharray="7 7" />
                  <polygon
                    points={`${x - 7},${y + (prevY > y ? -12 : 12)} ${x + 7},${y + (prevY > y ? -12 : 12)} ${x},${y + (prevY > y ? -2 : 2)}`}
                    fill="rgba(122,216,232,0.75)"
                  />
                </g>
              )}
              <circle cx={x} cy={y} r={7} fill={C.orange} />
              <text x={x} y={y - 26} textAnchor="middle" fill={C.paper} fontFamily={DISPLAY} fontSize={34} fontWeight={600}>
                {p.value.toFixed(2)}
              </text>
              <text x={x} y={box.top + box.height + 54} textAnchor="middle" fill="rgba(244,241,234,0.62)" fontFamily={FONT} fontSize={20} letterSpacing="0.08em">
                {p.label}
              </text>
              {p.note && (
                <text x={x} y={box.top + box.height + 84} textAnchor="middle" fill="rgba(244,241,234,0.42)" fontFamily={FONT} fontSize={18}>
                  {p.note}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div style={{position: 'absolute', left: 96, top: 892, color: 'rgba(244,241,234,0.55)', fontSize: 20, letterSpacing: '0.06em'}}>
        {note}
      </div>
      <div data-source="market" style={{position: 'absolute', left: 96, top: 934, width: 1500, color: 'rgba(244,241,234,0.66)', fontSize: 15}}>
        {source}
      </div>
    </SceneFrame>
  );
};
