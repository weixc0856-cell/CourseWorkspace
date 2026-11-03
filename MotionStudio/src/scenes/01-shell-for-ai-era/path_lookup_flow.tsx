import {Line, Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 8 — $PATH lookup from left to right.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍。
 * 时长约 12 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const queryBox = createRef<Rect>();
  const slot1 = createRef<Rect>();
  const slot2 = createRef<Rect>();
  const slot3 = createRef<Rect>();
  const status1 = createRef<Txt>();
  const status2 = createRef<Txt>();
  const status3 = createRef<Txt>();
  const executionArrow = createRef<Line>();

  view.add(
    <Node>
      <Txt
        text={'BINARY RESOLUTION: $PATH TRAVERSAL'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-280}
      />

      {/* 待查找指令 */}
      <Rect
        ref={queryBox}
        x={0}
        y={-140}
        width={340}
        height={70}
        radius={8}
        fill={MK.orangeSoft}
        stroke={MK.orange}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'Command: date'}
          fontFamily={MK_FONT_MONO}
          fontSize={24}
          fontWeight={700}
          fill={MK.orange}
        />
      </Rect>

      {/* 目录 Slot 1 */}
      <Rect
        ref={slot1}
        x={-320}
        y={40}
        width={270}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'1. /usr/local/bin'}
          y={-25}
          fontFamily={MK_FONT_MONO}
          fontSize={16}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          ref={status1}
          text={'Pending...'}
          y={25}
          fontFamily={MK_FONT_SANS}
          fontSize={15}
          fill={MK.muted}
        />
      </Rect>

      {/* 目录 Slot 2 */}
      <Rect
        ref={slot2}
        x={0}
        y={40}
        width={270}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'2. /usr/bin'}
          y={-25}
          fontFamily={MK_FONT_MONO}
          fontSize={16}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          ref={status2}
          text={'Pending...'}
          y={25}
          fontFamily={MK_FONT_SANS}
          fontSize={15}
          fill={MK.muted}
        />
      </Rect>

      {/* 目录 Slot 3 */}
      <Rect
        ref={slot3}
        x={320}
        y={40}
        width={270}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'3. /bin'}
          y={-25}
          fontFamily={MK_FONT_MONO}
          fontSize={16}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          ref={status3}
          text={'Pending...'}
          y={25}
          fontFamily={MK_FONT_SANS}
          fontSize={15}
          fill={MK.muted}
        />
      </Rect>

      {/* 命中后向上分发执行 */}
      <Line
        ref={executionArrow}
        points={[
          [320, -25],
          [320, -100],
          [170, -140],
        ]}
        stroke={MK.success}
        lineWidth={3}
        endArrow
        arrowSize={8}
        opacity={0}
      />
    </Node>,
  );

  // ---------- 时序 ----------
  yield* all(
    queryBox().opacity(1, 0.6),
    slot1().opacity(1, 0.6),
    slot2().opacity(1, 0.6),
    slot3().opacity(1, 0.6),
  );
  yield* waitFor(2.0);

  // Slot 1 — Miss
  yield* slot1().stroke(MK.orange, 0.3);
  status1().text('Checking...');
  yield* waitFor(0.3);
  slot1().stroke(MK.border);
  status1().text('✕ Miss (Not found)');
  status1().fill(MK.muted);
  yield* waitFor(0.5);

  // Slot 2 — Miss
  yield* slot2().stroke(MK.orange, 0.3);
  status2().text('Checking...');
  yield* waitFor(0.3);
  slot2().stroke(MK.border);
  status2().text('✕ Miss (Not found)');
  status2().fill(MK.muted);
  yield* waitFor(0.5);

  // Slot 3 — Hit
  yield* slot3().stroke(MK.orange, 0.3);
  status3().text('Checking...');
  yield* waitFor(0.3);
  status3().text('✓ Hit! (/bin/date)');
  yield* all(
    slot3().stroke(MK.success, 0.4),
    slot3().fill(MK.successSoft, 0.4),
    status3().fill(MK.success, 0.4),
  );
  yield* waitFor(1.0);

  // 停止搜索，向上分发执行
  yield* executionArrow().opacity(1, 0.5);
  yield* waitFor(0.5);
  yield* queryBox().scale(1.05, 0.25);
  yield* queryBox().scale(1.0, 0.25);
  yield* waitFor(3.6);
});
