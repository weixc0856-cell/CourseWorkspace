import {Circle, Line, Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 2 — GUI silos vs. CLI pipelines.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍填满画面，
 * 不重新排坐标。时长约 12 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const titleRef = createRef<Txt>();
  const guiGroup = createRef<Node>();
  const cliGroup = createRef<Node>();

  view.add(
    <Txt
      ref={titleRef}
      text={'INTERFACE PARADIGM COMPARISON'}
      fontFamily={MK_FONT_SANS}
      fontSize={24}
      fontWeight={700}
      fill={MK.muted}
      letterSpacing={2}
      y={-280}
      opacity={0}
    />,
  );

  // ---------- 第一幕：GUI 孤岛 ----------
  const appARef = createRef<Rect>();
  const appBRef = createRef<Rect>();
  const barrierLine = createRef<Line>();
  const barrierText = createRef<Txt>();

  view.add(
    <Node ref={guiGroup}>
      <Rect
        ref={appARef}
        x={-280}
        y={0}
        width={320}
        height={220}
        radius={12}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Rect y={-80} width={280} height={24} fill={MK.border} radius={4} />
        <Circle x={-120} y={-80} size={10} fill={MK.muted} />
        <Circle x={-100} y={-80} size={10} fill={MK.muted} />
        <Txt
          text={'Vendor App A (GUI)'}
          y={0}
          fontFamily={MK_FONT_SANS}
          fontSize={20}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          text={'Rigid Buttons & Closed UI'}
          y={36}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fill={MK.muted}
        />
      </Rect>

      <Rect
        ref={appBRef}
        x={280}
        y={0}
        width={320}
        height={220}
        radius={12}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Rect y={-80} width={280} height={24} fill={MK.border} radius={4} />
        <Circle x={-120} y={-80} size={10} fill={MK.muted} />
        <Circle x={-100} y={-80} size={10} fill={MK.muted} />
        <Txt
          text={'Vendor App B (GUI)'}
          y={0}
          fontFamily={MK_FONT_SANS}
          fontSize={20}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          text={'Isolated Data Format'}
          y={36}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fill={MK.muted}
        />
      </Rect>

      <Line
        ref={barrierLine}
        points={[
          [-100, 0],
          [100, 0],
        ]}
        stroke={MK.danger}
        lineWidth={3}
        lineDash={[8, 8]}
        opacity={0}
      />
      <Txt
        ref={barrierText}
        text={'Manual Copy-Paste / Blocked'}
        y={-30}
        fontFamily={MK_FONT_SANS}
        fontSize={16}
        fontWeight={600}
        fill={MK.danger}
        opacity={0}
      />
    </Node>,
  );

  // ---------- 第二幕：CLI 管道 ----------
  const pipeBoxRef = createRef<Rect>();
  const streamDataCircle = createRef<Circle>();

  view.add(
    <Node ref={cliGroup} opacity={0}>
      <Rect
        x={-280}
        y={0}
        width={260}
        height={140}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
      >
        <Txt
          text={'Tool A (CLI)'}
          y={-20}
          fontFamily={MK_FONT_MONO}
          fontSize={22}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'stdout (Raw Stream)'}
          y={24}
          fontFamily={MK_FONT_MONO}
          fontSize={14}
          fill={MK.muted}
        />
      </Rect>

      <Rect
        ref={pipeBoxRef}
        x={0}
        y={0}
        width={100}
        height={60}
        radius={6}
        fill={MK.orangeSoft}
        stroke={MK.orange}
        lineWidth={2}
      >
        <Txt
          text={'|'}
          y={-2}
          fontFamily={MK_FONT_MONO}
          fontSize={32}
          fontWeight={800}
          fill={MK.orange}
        />
      </Rect>

      <Rect
        x={280}
        y={0}
        width={260}
        height={140}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
      >
        <Txt
          text={'Tool B (CLI)'}
          y={-20}
          fontFamily={MK_FONT_MONO}
          fontSize={22}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'stdin (Processed Stream)'}
          y={24}
          fontFamily={MK_FONT_MONO}
          fontSize={14}
          fill={MK.muted}
        />
      </Rect>

      <Circle
        ref={streamDataCircle}
        x={-150}
        y={0}
        size={14}
        fill={MK.orange}
        opacity={0}
      />
    </Node>,
  );

  // ---------- 时序 ----------
  yield* all(
    titleRef().opacity(1, 0.8),
    appARef().opacity(1, 0.8),
    appARef().y(-20, 0.8),
    appBRef().opacity(1, 0.8),
    appBRef().y(-20, 0.8),
  );
  yield* waitFor(1.0);

  yield* all(
    barrierLine().opacity(1, 0.5),
    barrierText().opacity(1, 0.5),
    barrierText().y(-40, 0.5),
  );
  yield* waitFor(0.8);

  yield* titleRef().opacity(0, 0.2);
  titleRef().text('PARADIGM 1: GUI SILOS & VENDOR LOCK-IN');
  yield* all(titleRef().opacity(1, 0.4), waitFor(2.0));

  yield* all(guiGroup().opacity(0, 0.6), guiGroup().scale(0.95, 0.6));
  yield* waitFor(0.3);

  yield* titleRef().opacity(0, 0.2);
  titleRef().text('PARADIGM 2: CLI PIPELINES & UNIVERSAL STREAMS');
  yield* all(titleRef().opacity(1, 0.3), cliGroup().opacity(1, 0.6));

  yield* streamDataCircle().opacity(1, 0.2);
  for (let i = 0; i < 3; i++) {
    streamDataCircle().x(-150);
    yield* streamDataCircle().x(150, 1.2);
  }

  yield* all(
    pipeBoxRef().scale(1.1, 0.3),
    streamDataCircle().opacity(0, 0.3),
  );
  yield* pipeBoxRef().scale(1.0, 0.3);
  yield* waitFor(0.8);
});
