import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {assertSequenceDuration} from '../chapter/timing';
import {PhotoScene} from '../chapter/PhotoScene';
import {CarScene} from '../chapter/CarScene';
import {MechanismScene} from '../chapter/MechanismScene';
import {EvidenceScene} from '../chapter/EvidenceScene';
import {FormulaBlock} from '../components/FormulaBlock';
import {PointsCard} from '../components/PointsCard';
import timing from './timing.json';

// Every instance must name its own content. Components keep sample copy as
// defaults for the legacy Chapter composition, so an instance that omits a prop
// silently renders the opening card's picture and headline. That is how a
// twelve-minute film ended up showing one chart and one photograph throughout,
// with copy that belonged to the first act. Assembly fails instead.
const REQUIRED: Record<string, string[]> = {
  PhotoInsert: ['image', 'eyebrow', 'headline'],
  ChartOverlay: ['image', 'eyebrow', 'title', 'source'],
  MechanismDiagram: ['eyebrow', 'title'],
  CarFlowScene: ['eyebrow', 'headline'],
  FormulaBlock: ['tex', 'title'],
  PointsCard: ['eyebrow', 'title', 'points'],
};

// Figures are evidence: a mechanism or flow scene must either sit on an
// original book figure (base_image under staging/ref_figs) or declare why it
// is built from scratch. Assembly refuses anything else (CLAUDE.md §2.12).
const FIGURE_COMPONENTS = new Set(['MechanismDiagram', 'CarFlowScene']);
const CUSTOM_BUILD_REASONS = new Set(['formula_animation', 'summary_card', 'no_book_figure']);

const collectMissingProps = (beatId: string, index: number, instance: Instance, into: string[]) => {
  const props = (instance.props ?? {}) as Record<string, unknown>;
  for (const key of REQUIRED[instance.component] ?? []) {
    const value = props[key];
    if (value === undefined || value === null || value === '') {
      into.push(`${beatId}#${index} ${instance.component}.${key}`);
    }
  }
  if (FIGURE_COMPONENTS.has(instance.component)) {
    const base = props.base_image;
    const reason = props.custom_build_reason;
    const hasBase = typeof base === 'string' && base.startsWith('staging/ref_figs/');
    const hasReason = typeof reason === 'string' && CUSTOM_BUILD_REASONS.has(reason);
    if (!hasBase && !hasReason) {
      into.push(
        `${beatId}#${index} ${instance.component}: ${instance.component} requires base_image from ref_figs (CLAUDE.md §2.12)`,
      );
    }
  }
};

const COMPONENTS: Record<string, React.FC<any>> = {
  PhotoInsert: PhotoScene,
  CarFlowScene: CarScene,
  MechanismDiagram: MechanismScene,
  ChartOverlay: EvidenceScene,
  FormulaBlock: FormulaBlock,
  PointsCard: PointsCard,
};

// The audit compares this attribute with timing.json, so both sides use the
// same precedence order. An instance with no declared asset reports ''.
const ASSET_KEYS = ['asset', 'image', 'figure', 'src'];
const assetOf = (props?: Record<string, unknown>) => {
  for (const key of ASSET_KEYS) {
    const value = props ? props[key] : undefined;
    if (typeof value === 'string' && value) return value;
  }
  return '';
};

type Instance = {component: string; duration: number; props?: Record<string, unknown>};
type Beat = {id: string; seconds: number; instances: Instance[]};

export const Episode: React.FC = () => {
  const {fps} = useVideoConfig();
  let cursor = 0;
  const scenes: React.ReactNode[] = [];
  const missing: string[] = [];
  for (const beat of timing.beats as Beat[]) {
    for (const [index, instance] of beat.instances.entries()) {
      collectMissingProps(beat.id, index, instance, missing);
    }
  }
  if (missing.length) {
    throw new Error(
      `episode assembly: ${missing.length} required props are not set, so the components ` +
        `would fall back to the sample card's copy and picture:\n  ${missing.join('\n  ')}`,
    );
  }
  for (const beat of timing.beats as Beat[]) {
    for (const [index, instance] of beat.instances.entries()) {
      const frames = Math.round(instance.duration * fps);
      assertSequenceDuration(frames, fps, instance.duration);
      const Component = COMPONENTS[instance.component];
      if (!Component) throw new Error(`unknown component ${instance.component} in ${beat.id}`);
      const from = cursor;
      scenes.push(
        <Sequence key={`${beat.id}-${index}`} from={from} durationInFrames={frames}>
          <div
            data-beat-id={beat.id}
            data-instance-index={index}
            data-instance-component={instance.component}
            data-asset-src={assetOf(instance.props)}
            style={{position: 'absolute', inset: 0}}
          >
            <Component {...(instance.props ?? {})} duration={instance.duration} />
          </div>
        </Sequence>,
      );
      cursor += frames;
    }
  }
  return <AbsoluteFill style={{background: '#05070A'}}>{scenes}</AbsoluteFill>;
};
