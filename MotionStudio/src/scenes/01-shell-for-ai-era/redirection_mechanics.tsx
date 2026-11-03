import {Line, Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 12 — stdin/stdout/stderr and > versus >>.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍。
 * 时长约 13 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const procBox = createRef<Rect>();
  const fileBox = createRef<Rect>();
  const lineStdout = createRef<Line>();
  const redirSymbol = createRef<Txt>();
  const fileOldText = createRef<Txt>();
  const fileNewText = createRef<Txt>();

  view.add(
    <Node>
      <Txt
        text={'I/O DESCRIPTORS: STREAMS & REDIRECTION'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-280}
      />

      {/* 中心进程 */}
      <Rect
        ref={procBox}
        x={-280}
        y={-20}
        width={240}
        height={180}
        radius={10}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'Running Process'}
          y={-50}
          fontFamily={MK_FONT_SANS}
          fontSize={18}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'fd 0 : stdin (Keyboard)'}
          y={-10}
          fontFamily={MK_FONT_MONO}
          fontSize={13}
          fill={MK.muted}
        />
        <Txt
          text={'fd 1 : stdout (Data)'}
          y={20}
          fontFamily={MK_FONT_MONO}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
        />
        <Txt
          text={'fd 2 : stderr (Errors)'}
          y={50}
          fontFamily={MK_FONT_MONO}
          fontSize={13}
          fill={MK.danger}
        />
      </Rect>

      {/* 重定向操作符 */}
      <Txt
        ref={redirSymbol}
        text={'>'}
        x={-60}
        y={-55}
        fontFamily={MK_FONT_MONO}
        fontSize={44}
        fontWeight={800}
        fill={MK.orange}
        opacity={0}
      />

      {/* 目标文件 */}
      <Rect
        ref={fileBox}
        x={240}
        y={-20}
        width={300}
        height={220}
        radius={10}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Rect y={-80} width={270} height={26} fill={MK.border} radius={4}>
          <Txt
            text={'output.txt'}
            fontFamily={MK_FONT_MONO}
            fontSize={14}
            fontWeight={600}
            fill={MK.text}
          />
        </Rect>

        <Txt
          ref={fileOldText}
          text={'Existing log entry 01...'}
          y={-20}
          fontFamily={MK_FONT_MONO}
          fontSize={14}
          fill={MK.muted}
        />
        <Txt
          ref={fileNewText}
          text={'New data written!'}
          y={20}
          fontFamily={MK_FONT_MONO}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
          opacity={0}
        />
      </Rect>

      {/* stdout 轨道 */}
      <Line
        ref={lineStdout}
        points={[
          [-160, 0],
          [-90, 0],
          [-30, 0],
          [90, 0],
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
  yield* all(procBox().opacity(1, 0.6), fileBox().opacity(1, 0.6));
  yield* waitFor(2.0);

  yield* all(redirSymbol().opacity(1, 0.4), lineStdout().opacity(1, 0.4));
  yield* waitFor(1.5);

  // 单大于号：截断覆写
  yield* all(
    fileOldText().opacity(0.1, 0.4),
    fileOldText().scale(0.9, 0.4),
  );
  yield* all(
    fileNewText().opacity(1, 0.4),
    fileNewText().y(-20, 0.4),
  );
  yield* waitFor(2.0);

  // 双大于号：追加
  redirSymbol().text('>>');
  fileOldText().text('Previous data preserved');
  fileNewText().text('Appended to bottom');
  yield* all(
    fileOldText().opacity(1, 0.4),
    fileOldText().y(-35, 0.4),
    fileOldText().scale(1, 0.4),
    fileNewText().y(10, 0.4),
  );
  yield* waitFor(2.0);

  yield* fileBox().stroke(MK.orange, 0.3);
  yield* fileBox().stroke(MK.border, 0.3);
  yield* waitFor(2.7);
});
