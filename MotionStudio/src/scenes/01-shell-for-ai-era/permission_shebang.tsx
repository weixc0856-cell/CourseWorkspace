import {Line, Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 15 — chmod +x and the shebang handoff.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍。
 * 时长约 12 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const fileCard = createRef<Rect>();
  const permText = createRef<Txt>();
  const statusBadge = createRef<Rect>();
  const statusLabel = createRef<Txt>();
  const shebangBox = createRef<Rect>();
  const kernelArrow = createRef<Line>();

  view.add(
    <Node>
      <Txt
        text={'EXECUTION PRIVILEGE & THE SHEBANG MECHANISM'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-280}
      />

      {/* 脚本文件卡片 */}
      <Rect
        ref={fileCard}
        x={-240}
        y={0}
        width={340}
        height={220}
        radius={10}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'script.sh'}
          y={-70}
          fontFamily={MK_FONT_MONO}
          fontSize={20}
          fontWeight={700}
          fill={MK.text}
        />

        <Rect y={-10} width={280} height={42} radius={6} fill={MK.border}>
          <Txt
            ref={permText}
            text={'-rw-r--r--'}
            fontFamily={MK_FONT_MONO}
            fontSize={18}
            fontWeight={600}
            fill={MK.text}
          />
        </Rect>

        <Rect
          ref={statusBadge}
          y={60}
          width={220}
          height={32}
          radius={4}
          fill={MK.dangerSoft}
        >
          <Txt
            ref={statusLabel}
            text={'Permission Denied'}
            fontFamily={MK_FONT_SANS}
            fontSize={13}
            fontWeight={600}
            fill={MK.danger}
          />
        </Rect>
      </Rect>

      {/* Shebang 引导 */}
      <Rect
        ref={shebangBox}
        x={240}
        y={0}
        width={340}
        height={220}
        radius={10}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'Header Dispatch'}
          y={-70}
          fontFamily={MK_FONT_SANS}
          fontSize={18}
          fontWeight={700}
          fill={MK.text}
        />

        <Rect
          y={-10}
          width={280}
          height={42}
          radius={6}
          fill={MK.orangeSoft}
          stroke={MK.orange}
          lineWidth={1}
        >
          <Txt
            text={'#!/bin/bash'}
            fontFamily={MK_FONT_MONO}
            fontSize={18}
            fontWeight={700}
            fill={MK.orange}
          />
        </Rect>

        <Txt
          text={'Kernel dispatches interpreter'}
          y={55}
          fontFamily={MK_FONT_SANS}
          fontSize={13}
          fill={MK.muted}
        />
      </Rect>

      {/* 内核引导连接 */}
      <Line
        ref={kernelArrow}
        points={[
          [-70, 0],
          [70, 0],
        ]}
        stroke={MK.orange}
        lineWidth={3}
        endArrow
        arrowSize={8}
        opacity={0}
      />
    </Node>,
  );

  // ---------- 时序 ----------
  yield* all(fileCard().opacity(1, 0.6), fileCard().y(-10, 0.6));
  yield* waitFor(3.4);

  // chmod +x
  permText().text('-rwxr-xr-x');
  statusLabel().text('Executable Granted (chmod +x)');
  yield* all(
    permText().fill(MK.orange, 0.4),
    statusBadge().fill(MK.successSoft, 0.4),
    statusLabel().fill(MK.success, 0.4),
    fileCard().stroke(MK.success, 0.4),
  );
  yield* waitFor(2.5);

  // Shebang 解释器分发
  yield* all(
    shebangBox().opacity(1, 0.6),
    shebangBox().y(-10, 0.6),
    kernelArrow().opacity(1, 0.6),
  );
  yield* waitFor(2.0);

  yield* shebangBox().scale(1.03, 0.3);
  yield* shebangBox().scale(1.0, 0.3);
  yield* waitFor(2.0);
});
