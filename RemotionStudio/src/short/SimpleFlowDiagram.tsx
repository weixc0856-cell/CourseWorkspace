import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveColor, resolveTheme} from './theme';
import type {FlowProps} from './types';

const Arrow: React.FC<{color: string; vertical: boolean; opacity: number}> = ({
  color,
  vertical,
  opacity,
}) => (
  <div
    style={{
      flex: 'none',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: vertical ? '100%' : 72,
      height: vertical ? 64 : '100%',
      opacity,
      color,
      fontSize: 44,
      lineHeight: 1,
    }}
  >
    {vertical ? '↓' : '→'}
  </div>
);

export const SimpleFlowDiagram: React.FC<FlowProps & {themeName?: string}> = ({
  title,
  steps,
  direction,
  footer,
  themeName,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const theme = resolveTheme(themeName);
  const vertical = direction ? direction === 'vertical' : height > width;
  return (
    <AbsoluteFill
      style={{
        background: theme.paper,
        color: theme.ink,
        fontFamily: theme.sans,
        padding: vertical ? '150px 64px 280px' : '90px 120px 160px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 36,
      }}
    >
      {title ? <div style={{fontSize: 42, fontWeight: 700, lineHeight: 1.15}}>{title}</div> : null}
      <div
        style={{
          display: 'flex',
          flexDirection: vertical ? 'column' : 'row',
          alignItems: vertical ? 'stretch' : 'center',
          justifyContent: 'space-between',
          gap: vertical ? 8 : 8,
        }}
      >
        {steps.map((step, index) => {
          const progress = spring({
            frame: frame - index * 10,
            fps,
            config: {damping: 200, mass: 0.7},
          });
          const accent =
            resolveColor(theme, step.accent) ||
            [theme.accent, theme.blue, theme.teal, theme.purple][index % 4];
          return (
            <React.Fragment key={step.label}>
              {index > 0 ? (
                <Arrow
                  color={theme.border}
                  vertical={vertical}
                  opacity={interpolate(progress, [0, 1], [0, 1])}
                />
              ) : null}
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  borderTop: `6px solid ${accent}`,
                  background: theme.surface,
                  padding: vertical ? '26px 30px' : '30px 32px',
                  opacity: progress,
                  transform: `translateY(${interpolate(progress, [0, 1], [24, 0])}px)`,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{fontSize: 32, fontWeight: 700, lineHeight: 1.2}}>{step.label}</div>
                {step.detail ? (
                  <div style={{fontSize: 24, lineHeight: 1.35, color: theme.body}}>{step.detail}</div>
                ) : null}
              </div>
            </React.Fragment>
          );
        })}
      </div>
      {footer ? <div style={{fontSize: 26, color: theme.muted}}>{footer}</div> : null}
    </AbsoluteFill>
  );
};
