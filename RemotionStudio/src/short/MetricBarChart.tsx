import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveColor, resolveTheme} from './theme';
import type {MetricBarProps} from './types';

export const MetricBarChart: React.FC<MetricBarProps & {themeName?: string}> = ({
  title,
  data,
  max,
  unit,
  source,
  note,
  themeName,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const theme = resolveTheme(themeName);
  const vertical = height > width;
  const ceiling = max || Math.max(...data.map((item) => item.value), 1);
  const chartHeight = vertical ? 620 : 520;
  return (
    <AbsoluteFill
      style={{
        background: theme.paper,
        color: theme.ink,
        fontFamily: theme.sans,
        padding: vertical ? '160px 72px 330px' : '90px 160px 270px',
        display: 'flex',
        flexDirection: 'column',
        gap: 40,
      }}
    >
      {title ? <div style={{fontSize: 44, fontWeight: 700, lineHeight: 1.15}}>{title}</div> : null}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-around',
          gap: 28,
          height: chartHeight,
          borderBottom: `2px solid ${theme.border}`,
          paddingBottom: 8,
        }}
      >
        {data.map((item, index) => {
          const progress = spring({
            frame: frame - index * 8,
            fps,
            config: {damping: 200, mass: 0.7},
          });
          const color =
            resolveColor(theme, item.color) ||
            [theme.accent, theme.blue, theme.teal, theme.purple][index % 4];
          const barHeight = Math.max(16, (item.value / ceiling) * (chartHeight - 90) * progress);
          return (
            <div
              key={item.label}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 14,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  fontSize: 40,
                  fontWeight: 700,
                  color: theme.ink,
                  opacity: interpolate(progress, [0.4, 1], [0, 1], {
                    extrapolateLeft: 'clamp',
                    extrapolateRight: 'clamp',
                  }),
                }}
              >
                {item.display ?? `${item.value}${unit ? ` ${unit}` : ''}`}
              </div>
              <div style={{width: '72%', height: barHeight, background: color, borderRadius: 2}} />
              <div
                style={{
                  fontSize: 26,
                  lineHeight: 1.2,
                  color: theme.body,
                  textAlign: 'center',
                  maxWidth: '100%',
                }}
              >
                {item.label}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 24}}>
        <div style={{fontSize: 24, color: theme.muted}}>{note || ''}</div>
        <div style={{fontSize: 22, color: theme.muted, textAlign: 'right'}}>{source || ''}</div>
      </div>
    </AbsoluteFill>
  );
};
