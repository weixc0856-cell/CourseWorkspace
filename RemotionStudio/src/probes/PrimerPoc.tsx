import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import data from '../data/primer-poc.json';

type Species = {name: string; hex: string};

export type PrimerPocProps = {
  seed: number;
  frames: number;
  fps: number;
  mutation: number;
  matrix: number[][];
  species: Species[];
  fractions: number[][];
  engineLabel?: string;
};

const BG = '#2D3033';
const TEXT = '#F2F0E9';
const MUTED = '#9AA0A6';
const LINE = '#5E646B';
const SERIF = 'Georgia, "Times New Roman", serif';

const TRI = {
  S: {x: 330, y: 280},
  R: {x: 110, y: 700},
  P: {x: 550, y: 700},
};

const barycentric = (fraction: number[]) => {
  const [r, p, s] = fraction;
  return {
    x: r * TRI.R.x + p * TRI.P.x + s * TRI.S.x,
    y: r * TRI.R.y + p * TRI.P.y + s * TRI.S.y,
  };
};

const cellStyle: React.CSSProperties = {
  height: 38,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderBottom: '1px solid #41464C',
  fontFamily: SERIF,
  fontSize: 22,
};

export const PrimerPoc: React.FC<PrimerPocProps> = (props) => {
  const frame = useCurrentFrame();
  const index = Math.min(props.frames - 1, Math.max(0, frame));
  const fraction = props.fractions[index];
  const point = barycentric(fraction);
  const dominant = fraction.indexOf(Math.max(...fraction));
  const trail = props.fractions
    .slice(0, index + 1)
    .filter((_, i) => i % 6 === 0 || i === index)
    .map(barycentric);
  const path = trail.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  return (
    <AbsoluteFill style={{backgroundColor: BG, color: TEXT}}>
      <div
        style={{
          position: 'absolute',
          left: 640,
          top: 190,
          width: 1220,
          height: 686,
          overflow: 'hidden',
        }}
      >
        <OffthreadVideo
          src={staticFile('staging/primer-poc/world.mp4')}
          style={{width: '100%', height: '100%', objectFit: 'cover'}}
          muted
        />
      </div>

      <div
        style={{
          position: 'absolute',
          left: 70,
          top: 80,
          fontFamily: SERIF,
          fontSize: 46,
          lineHeight: 1.08,
          letterSpacing: 0.5,
        }}
      >
        Rock · Paper · Scissors
      </div>
      <div
        style={{
          position: 'absolute',
          left: 72,
          top: 205,
          fontFamily: SERIF,
          fontSize: 19,
          color: MUTED,
          fontStyle: 'italic',
        }}
      >
        a 30-second agent simulation
      </div>

      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        <polygon
          points={`${TRI.S.x},${TRI.S.y} ${TRI.R.x},${TRI.R.y} ${TRI.P.x},${TRI.P.y}`}
          fill="rgba(255,255,255,0.02)"
          stroke={LINE}
          strokeWidth={1.5}
        />
        <polyline points={path} fill="none" stroke="#D9D4C5" strokeWidth={2.2} opacity={0.9} />
        <circle cx={point.x} cy={point.y} r={9} fill={props.species[dominant].hex} stroke={TEXT} strokeWidth={2} />
      </svg>

      <div style={{position: 'absolute', left: 286, top: 238, fontFamily: SERIF, fontSize: 26, color: props.species[2].hex}}>
        Scissors
      </div>
      <div style={{position: 'absolute', left: 78, top: 708, fontFamily: SERIF, fontSize: 26, color: props.species[0].hex}}>
        Rock
      </div>
      <div style={{position: 'absolute', left: 504, top: 708, fontFamily: SERIF, fontSize: 26, color: props.species[1].hex}}>
        Paper
      </div>

      <div style={{position: 'absolute', left: 78, top: 762, fontFamily: SERIF, fontSize: 21, color: TEXT}}>
        payoff
      </div>
      <div
        style={{
          position: 'absolute',
          left: 78,
          top: 798,
          width: 462,
          display: 'grid',
          gridTemplateColumns: '120px repeat(3, 114px)',
        }}
      >
        <div style={{...cellStyle, color: MUTED, fontSize: 17}} />
        {props.species.map((item) => (
          <div key={`h-${item.name}`} style={{...cellStyle, color: item.hex, fontSize: 18}}>
            {item.name}
          </div>
        ))}
        {props.matrix.map((row, i) => (
          <React.Fragment key={`row-${i}`}>
            <div style={{...cellStyle, justifyContent: 'flex-start', color: props.species[i].hex, fontSize: 18}}>
              {props.species[i].name}
            </div>
            {row.map((value, j) => (
              <div
                key={`cell-${i}-${j}`}
                style={{
                  ...cellStyle,
                  color: value === 1 ? TEXT : value === 0.5 ? '#A9AFB5' : '#767C82',
                }}
              >
                {value.toFixed(1).replace('.0', '')}
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>
      <div style={{position: 'absolute', left: 78, top: 1005, fontFamily: SERIF, fontSize: 18, color: MUTED}}>
        mutation rate: 1 in {(1 / props.mutation).toFixed(0)}
      </div>

      <div
        style={{
          position: 'absolute',
          left: 640,
          top: 118,
          width: 1220,
          height: 1,
          backgroundColor: '#41464C',
        }}
      />
      <div style={{position: 'absolute', left: 1540, top: 912, fontFamily: SERIF, fontSize: 14, color: MUTED}}>
        {props.engineLabel ?? 'Blender Eevee'} · deterministic seed {props.seed}
      </div>
    </AbsoluteFill>
  );
};

export const primerPocDefaults = data as PrimerPocProps;
