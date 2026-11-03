import {Line, Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, sequence, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 6 — whitespace tokenization and argv dispatch.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍。
 * 时长约 11 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const rawInputBox = createRef<Rect>();
  const cutLine1 = createRef<Line>();
  const cutLine2 = createRef<Line>();

  const token0 = createRef<Rect>();
  const token1 = createRef<Rect>();
  const token2 = createRef<Rect>();

  view.add(
    <Node>
      <Txt
        text={'SHELL PARSER: WHITESPACE TOKENIZATION'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-280}
      />

      {/* 原始输入行 */}
      <Rect
        ref={rawInputBox}
        x={0}
        y={-140}
        width={720}
        height={80}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'echo'}
          x={-220}
          fontFamily={MK_FONT_MONO}
          fontSize={28}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          text={'Hello'}
          x={-30}
          fontFamily={MK_FONT_MONO}
          fontSize={28}
          fontWeight={600}
          fill={MK.text}
        />
        <Txt
          text={'World'}
          x={210}
          fontFamily={MK_FONT_MONO}
          fontSize={28}
          fontWeight={600}
          fill={MK.text}
        />
      </Rect>

      {/* 切词虚线 */}
      <Line
        ref={cutLine1}
        points={[
          [-140, -190],
          [-140, -90],
        ]}
        stroke={MK.orange}
        lineWidth={3}
        lineDash={[6, 6]}
        opacity={0}
      />
      <Line
        ref={cutLine2}
        points={[
          [80, -190],
          [80, -90],
        ]}
        stroke={MK.orange}
        lineWidth={3}
        lineDash={[6, 6]}
        opacity={0}
      />

      {/* argv 参数槽位 */}
      <Rect
        ref={token0}
        x={-240}
        y={120}
        width={200}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.orange}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'argv[0] · Command'}
          y={-35}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
        />
        <Txt
          text={'echo'}
          y={15}
          fontFamily={MK_FONT_MONO}
          fontSize={26}
          fontWeight={700}
          fill={MK.text}
        />
      </Rect>

      <Rect
        ref={token1}
        x={0}
        y={120}
        width={200}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'argv[1] · Param'}
          y={-35}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.muted}
        />
        <Txt
          text={'Hello'}
          y={15}
          fontFamily={MK_FONT_MONO}
          fontSize={26}
          fontWeight={700}
          fill={MK.text}
        />
      </Rect>

      <Rect
        ref={token2}
        x={240}
        y={120}
        width={200}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'argv[2] · Param'}
          y={-35}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.muted}
        />
        <Txt
          text={'World'}
          y={15}
          fontFamily={MK_FONT_MONO}
          fontSize={26}
          fontWeight={700}
          fill={MK.text}
        />
      </Rect>
    </Node>,
  );

  // ---------- 时序 ----------
  yield* all(
    rawInputBox().opacity(1, 0.6),
    rawInputBox().y(-120, 0.6),
  );
  yield* waitFor(2.0);

  yield* all(
    cutLine1().opacity(1, 0.4),
    cutLine2().opacity(1, 0.4),
  );
  yield* waitFor(1.5);

  yield* sequence(
    0.2,
    all(token0().opacity(1, 0.5), token0().y(100, 0.5)),
    all(token1().opacity(1, 0.5), token1().y(100, 0.5)),
    all(token2().opacity(1, 0.5), token2().y(100, 0.5)),
  );
  yield* waitFor(2.0);

  yield* token0().scale(1.05, 0.3);
  yield* token0().scale(1.0, 0.3);
  yield* waitFor(2.0);
});
