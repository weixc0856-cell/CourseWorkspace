import React from 'react';
import {AbsoluteFill, Img, Sequence, staticFile, useVideoConfig} from 'remotion';
import {BigDate} from '../components/BigDate';
import {Statement} from '../components/Statement';
import {Chain} from '../components/Chain';
import {NotClaimed} from '../components/NotClaimed';
import {EndCard} from '../components/EndCard';
import {MarketChart} from '../components/MarketChart';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, FONT} from '../chapter/theme';
import proof from './proof.json';

type Entry = {
  id: string;
  kind: string;
  start_s: number;
  duration_s: number;
  renderer?: string;
  text?: string;
  tier?: string;
  source?: string;
  image?: string | null;
};

export type NewsEpisodeProps = {
  fps: number;
  duration_s: number;
  entries: Entry[];
};

const CARDS: Record<string, React.FC<any>> = {
  BigDate,
  Statement,
  Chain,
  NotClaimed,
  EndCard,
};

const MARKET_SOURCE = 'Exchange close data via Reuters / Bloomberg · fact-check F12 / F13';

const FootageScene: React.FC<{image: string; source?: string; tier?: string}> = ({image, source, tier}) => {
  const frame = AbsoluteFill;
  return (
    <SceneFrame style={{background: '#05070A', fontFamily: FONT}}>
      <Img
        src={staticFile(image)}
        style={{position: 'absolute', left: 96, top: 120, width: 1728, height: 760, objectFit: 'cover', objectPosition: 'top center', boxShadow: '0 30px 90px rgba(0,0,0,0.55)'}}
      />
      <div style={{position: 'absolute', left: 96, bottom: 150, color: 'rgba(244,241,234,0.66)', fontSize: 17}}>{source}</div>
      {tier ? <div style={{position: 'absolute', right: 96, bottom: 150, color: C.cyan, fontSize: 17, letterSpacing: '0.2em'}}>{tier}</div> : null}
    </SceneFrame>
  );
};

export const NewsEpisode: React.FC<NewsEpisodeProps> = ({fps, duration_s, entries}) => {
  useVideoConfig();
  const total = Math.round(duration_s * fps);
  return (
    <AbsoluteFill style={{background: '#05070A'}}>
      {entries.map((entry) => {
        const from = Math.round(entry.start_s * fps);
        const want = Math.round(entry.duration_s * fps);
        const frames = Math.max(1, Math.min(want, total - from));
        if (frames <= 0) return null;
        const card = entry.renderer ? CARDS[entry.renderer] : undefined;
        let body: React.ReactNode;
        if (card) {
          const Card = card;
          body = <Card text={entry.text} tier={entry.tier} source={entry.source} />;
        } else if (entry.renderer === 'MarketChart') {
          body = <MarketChart source={MARKET_SOURCE} />;
        } else if (entry.image) {
          body = <FootageScene image={entry.image} source={entry.source} tier={entry.tier} />;
        } else {
          body = <Statement text={entry.text} tier={entry.tier} source={entry.source} />;
        }
        return (
          <Sequence key={entry.id} from={from} durationInFrames={frames} name={entry.id}>
            {body}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const defaultNewsProps = proof as NewsEpisodeProps;
