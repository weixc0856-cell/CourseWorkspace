import {Circle, Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, chain, createRef, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 11 — the Unix pipe as an in-memory kernel buffer.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍。
 * 时长约 13 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const proc1Ref = createRef<Rect>();
  const proc2Ref = createRef<Rect>();
  const pipeRef = createRef<Rect>();
  const diskIndicator = createRef<Rect>();
  const dataDot1 = createRef<Circle>();
  const dataDot2 = createRef<Circle>();

  view.add(
    <Node>
      <Txt
        text={'INTER-PROCESS COMMUNICATION: THE UNIX PIPE'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-280}
      />

      {/* 进程 A */}
      <Rect
        ref={proc1Ref}
        x={-340}
        y={-30}
        width={240}
        height={160}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'Process A (grep)'}
          y={-35}
          fontFamily={MK_FONT_MONO}
          fontSize={20}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'Running in memory'}
          y={5}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fill={MK.muted}
        />
        <Rect y={50} width={180} height={28} radius={4} fill={MK.border}>
          <Txt
            text={'stdout (fd 1)'}
            fontFamily={MK_FONT_MONO}
            fontSize={13}
            fill={MK.text}
          />
        </Rect>
      </Rect>

      {/* 内核管道缓冲区 */}
      <Rect
        ref={pipeRef}
        x={0}
        y={-30}
        width={240}
        height={100}
        radius={12}
        fill={MK.orangeSoft}
        stroke={MK.orange}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={"Kernel Pipe '|'"}
          y={-20}
          fontFamily={MK_FONT_MONO}
          fontSize={16}
          fontWeight={700}
          fill={MK.orange}
        />
        <Txt
          text={'In-memory · Linux 64 KB default'}
          y={15}
          fontFamily={MK_FONT_SANS}
          fontSize={13}
          fill={MK.muted}
        />
      </Rect>

      {/* 进程 B */}
      <Rect
        ref={proc2Ref}
        x={340}
        y={-30}
        width={240}
        height={160}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'Process B (sort)'}
          y={-35}
          fontFamily={MK_FONT_MONO}
          fontSize={20}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'Running in memory'}
          y={5}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fill={MK.muted}
        />
        <Rect y={50} width={180} height={28} radius={4} fill={MK.border}>
          <Txt
            text={'stdin (fd 0)'}
            fontFamily={MK_FONT_MONO}
            fontSize={13}
            fill={MK.text}
          />
        </Rect>
      </Rect>

      {/* 零落盘说明 */}
      <Rect
        ref={diskIndicator}
        x={0}
        y={200}
        width={600}
        height={60}
        radius={6}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={1}
        opacity={0}
      >
        <Txt
          text={'✓ Zero Disk I/O: Data streams directly via RAM without temporary files.'}
          fontFamily={MK_FONT_SANS}
          fontSize={15}
          fontWeight={600}
          fill={MK.success}
        />
      </Rect>

      {/* 数据流粒子 */}
      <Circle
        ref={dataDot1}
        x={-220}
        y={0}
        size={12}
        fill={MK.orange}
        opacity={0}
      />
      <Circle
        ref={dataDot2}
        x={-220}
        y={0}
        size={12}
        fill={MK.orange}
        opacity={0}
      />
    </Node>,
  );

  // ---------- 时序 ----------
  yield* all(
    proc1Ref().opacity(1, 0.6),
    proc1Ref().y(-10, 0.6),
    proc2Ref().opacity(1, 0.6),
    proc2Ref().y(-10, 0.6),
  );
  yield* waitFor(2.0);

  pipeRef().scale(0.95);
  yield* all(
    pipeRef().opacity(1, 0.5),
    pipeRef().scale(1.0, 0.5),
    diskIndicator().opacity(1, 0.5),
  );
  yield* waitFor(2.0);

  yield* all(dataDot1().opacity(1, 0.2), dataDot2().opacity(1, 0.2));
  yield* waitFor(1.0);

  for (let i = 0; i < 2; i++) {
    yield* all(
      dataDot1().x(220, 1.2),
      chain(dataDot2().x(-220, 0), dataDot2().x(220, 1.2)),
    );
    dataDot1().x(-220);
  }
  yield* waitFor(2.0);

  yield* all(
    dataDot1().opacity(0, 0.3),
    dataDot2().opacity(0, 0.3),
    pipeRef().scale(1.04, 0.3),
  );
  yield* pipeRef().scale(1.0, 0.3);
  yield* waitFor(2.0);
});
