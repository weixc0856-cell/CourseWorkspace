import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {BRAND} from '../brand/tokens';
import {FONTS} from '../styles/tokens';
import {BrandMark, CenteredLockup} from '../brand/BrandMark';
import {fitFontSize} from '../brand/layout';

/**
 * Centered brand frames — probe (owner rejection of BrandCourseIntro/Outro:
 * "没有居中"). This file is additive: it registers its own compositions and
 * touches no existing brand component or course composition.
 *
 * Layout law for both frames: every row is centred on x = 960, and the intro
 * title's line-box centre sits on y = 540 exactly (top: 540 +
 * translateY(-50%)). Letterspaced rows carry a negative right margin equal to
 * the tracking, so the ink box — not the padded box — is what centres.
 *
 * Motion law: one strong ease-out, cubic-bezier(0.16, 1, 0.3, 1), expressed
 * as track-in (letterSpacing tightening) and fades. No horizontal drift, no
 * off-centre parallax, no left alignment anywhere.
 */

const EASE = Easing.bezier(0.16, 1, 0.3, 1);

const enter = (frame: number, start: number, end: number): number =>
  interpolate(frame, [start, end], [0, 1], {
    easing: EASE,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

/** Centre one row on the frame's vertical axis, anchored at a given y. */
const centerRow: React.CSSProperties = {
  position: 'absolute',
  left: 0,
  right: 0,
  display: 'flex',
  justifyContent: 'center',
};

const IntroCentered: React.FC<{
  title: string;
  category: string;
  tagline: string;
}> = ({title, category, tagline}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const at = (seconds: number) => Math.round(seconds * fps);

  const mark = enter(frame, at(0.0), at(0.8));
  const word = enter(frame, at(0.07), at(0.55));
  const eyebrow = enter(frame, at(0.33), at(1.13));
  const titleIn = enter(frame, at(0.53), at(1.47));
  const rule = enter(frame, at(1.2), at(1.7));
  const taglineIn = enter(frame, at(1.4), at(1.93));

  const titleSize = fitFontSize(title, 1500, [92, 84, 76, 68]);

  // Eyebrow and tagline mirror each other ±150 px around the title centre;
  // the accent rule punctuates the tagline at +104.
  return (
    <AbsoluteFill style={{backgroundColor: BRAND.background}}>
      {/* wordmark, small, centred top */}
      <div style={{...centerRow, top: 84, alignItems: 'center', gap: 14}}>
        <BrandMark width={46} progress={mark} strokeWidth={22} />
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 28,
            fontWeight: 700,
            lineHeight: 1,
            letterSpacing: '-0.025em',
            marginRight: '0.025em',
            color: BRAND.ink,
            opacity: word,
            whiteSpace: 'nowrap',
          }}
        >
          {BRAND.identity.name}
        </div>
      </div>

      {/* eyebrow: small-caps, wide tracking, tracks in */}
      <div style={{...centerRow, top: 540 - 150, transform: 'translateY(-50%)'}}>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 20,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: `${0.5 - 0.16 * eyebrow}em`,
            marginRight: '-0.34em',
            color: BRAND.muted,
            opacity: eyebrow,
            whiteSpace: 'nowrap',
          }}
        >
          {category}
        </div>
      </div>

      {/* title: dead centre, both axes */}
      <div
        style={{
          ...centerRow,
          top: 540,
          transform: 'translateY(-50%)',
        }}
      >
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: titleSize,
            fontWeight: 700,
            lineHeight: 1.05,
            letterSpacing: `${0.02 - 0.05 * titleIn}em`,
            marginRight: '-0.03em',
            color: BRAND.ink,
            textAlign: 'center',
            maxWidth: 1600,
            opacity: titleIn,
            transform: `translateY(${(1 - titleIn) * 14}px)`,
          }}
        >
          {title}
        </div>
      </div>

      {/* accent rule, grows from the centre line */}
      <div style={{...centerRow, top: 540 + 104}}>
        <div
          style={{
            width: 72,
            height: 2,
            backgroundColor: BRAND.accent,
            transform: `scaleX(${rule})`,
            transformOrigin: 'center',
          }}
        />
      </div>

      {/* tagline, centred below */}
      <div style={{...centerRow, top: 540 + 152, transform: 'translateY(-50%)'}}>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 18,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: `${0.45 - 0.21 * taglineIn}em`,
            marginRight: '-0.24em',
            color: BRAND.muted,
            opacity: taglineIn,
            whiteSpace: 'nowrap',
          }}
        >
          {tagline}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const CenteredIntro: React.FC<{
  title?: string;
  category?: string;
  tagline?: string;
}> = ({
  title = 'From Silicon to Intelligence',
  category = 'HOW COMPUTE WORKS',
  tagline = BRAND.identity.tagline,
}) => <IntroCentered title={title} category={category} tagline={tagline} />;

export const CenteredOutro: React.FC<{}> = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const at = (seconds: number) => Math.round(seconds * fps);

  const thanks = enter(frame, at(0.13), at(0.8));
  const rule = enter(frame, at(0.53), at(1.0));
  const cta = enter(frame, at(0.73), at(1.3));
  const lock = enter(frame, at(0.93), at(1.6));

  return (
    <AbsoluteFill
      style={{
        backgroundColor: BRAND.background,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 48,
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: '-0.015em',
            marginRight: '0.015em',
            color: BRAND.ink,
            opacity: thanks,
            transform: `translateY(${(1 - thanks) * 10}px)`,
          }}
        >
          {BRAND.identity.thanks}
        </div>

        <div
          style={{
            marginTop: 36,
            width: 88,
            height: 2,
            backgroundColor: BRAND.accent,
            transform: `scaleX(${rule})`,
            transformOrigin: 'center',
          }}
        />

        <div
          style={{
            marginTop: 30,
            fontFamily: FONTS.sans,
            fontSize: 28,
            fontWeight: 400,
            letterSpacing: '0.01em',
            color: BRAND.muted,
            opacity: cta,
            transform: `translateY(${(1 - cta) * 8}px)`,
          }}
        >
          {BRAND.identity.cta}
        </div>

        <div style={{marginTop: 72, opacity: lock}}>
          <CenteredLockup
            wordSize={52}
            progress={1}
            taglineProgress={1}
            markProgress={lock}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};
