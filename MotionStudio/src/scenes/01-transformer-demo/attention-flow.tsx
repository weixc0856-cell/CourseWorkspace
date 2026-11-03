import {Line, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, easeOutCubic, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * 自注意力：token 序列进入注意力核，输出上下文向量。
 * 这是 Motion Canvas 的典型场景——离散结构、盒子与箭头、时间轴编排。
 *
 * 画布 1920×1080，时长约 6 秒。
 */

const TOKENS = ['The', 'cat', 'sat', 'down'];

const CHIP_W = 280;
const CHIP_H = 96;
const CHIP_GAP = 24;
const COL_X = -640;
const COL_CENTER_Y = -40;

const tokenY = (index: number) =>
  COL_CENTER_Y + (index - (TOKENS.length - 1) / 2) * (CHIP_H + CHIP_GAP);

export default makeScene2D(function* (view) {
  view.fill(MK.white);

  // 标题
  const title = createRef<Txt>();
  view.add(
    <Txt
      ref={title}
      text={'Self-Attention: tokens in, weights out'}
      y={-450}
      fill={MK.text}
      fontFamily={MK_FONT_SANS}
      fontSize={54}
      fontWeight={600}
      opacity={0}
    />,
  );

  // 左侧 token 序列
  const chips = TOKENS.map(() => createRef<Rect>());
  view.add(
    <>
      {TOKENS.map((token, index) => (
        <Rect
          ref={chips[index]}
          x={COL_X}
          y={tokenY(index)}
          width={CHIP_W}
          height={CHIP_H}
          radius={12}
          layout
          fill={MK.white}
          stroke={MK.border}
          lineWidth={2}
          justifyContent={'center'}
          alignItems={'center'}
          opacity={0}
        >
          <Txt
            text={token}
            fill={MK.text}
            fontFamily={MK_FONT_SANS}
            fontSize={40}
          />
        </Rect>
      ))}
    </>
  );

  // 每个 token 指向注意力核的箭头
  const arrows = TOKENS.map(() => createRef<Line>());
  view.add(
    <>
      {TOKENS.map((_, index) => (
        <Line
          ref={arrows[index]}
          points={[
            [COL_X + CHIP_W / 2 + 8, tokenY(index)],
            [-240, (index - (TOKENS.length - 1) / 2) * 44],
          ]}
          stroke={MK.muted}
          lineWidth={2.5}
          endArrow
          arrowSize={12}
          end={0}
        />
      ))}
    </>
  );

  // 注意力核
  const kernel = createRef<Rect>();
  view.add(
    <Rect
      ref={kernel}
      width={440}
      height={260}
      radius={18}
      layout
      fill={MK.white}
      stroke={MK.orange}
      lineWidth={3}
      direction={'column'}
      justifyContent={'center'}
      alignItems={'center'}
      gap={14}
      scale={0.92}
      opacity={0}
    >
      <Txt
        text={'Attention'}
        fill={MK.text}
        fontFamily={MK_FONT_SANS}
        fontSize={46}
        fontWeight={600}
      />
      <Txt
        text={'softmax(QKᵀ / √d) · V'}
        fill={MK.muted}
        fontFamily={MK_FONT_SANS}
        fontSize={26}
      />
    </Rect>
  );

  // 右侧输出
  const outArrow = createRef<Line>();
  const outChip = createRef<Rect>();
  view.add(
    <>
      <Line
        ref={outArrow}
        points={[
          [228, 0],
          [470, -60],
        ]}
        stroke={MK.orange}
        lineWidth={3}
        endArrow
        arrowSize={14}
        end={0}
      />
      <Rect
        ref={outChip}
        x={640}
        y={-60}
        width={300}
        height={120}
        radius={12}
        layout
        fill={MK.orangeSoft}
        stroke={MK.orange}
        lineWidth={2}
        justifyContent={'center'}
        alignItems={'center'}
        opacity={0}
      >
        <Txt
          text={'context vector'}
          fill={MK.text}
          fontFamily={MK_FONT_SANS}
          fontSize={30}
        />
      </Rect>
    </>
  );

  // 编排
  yield* title().opacity(1, 0.6, easeOutCubic);

  yield* all(
    ...chips.map((chip, index) =>
      (function* () {
        yield* waitFor(index * 0.12);
        yield* chip().opacity(1, 0.35, easeOutCubic);
      })(),
    ),
  );

  yield* all(
    ...arrows.map((arrow, index) =>
      (function* () {
        yield* waitFor(index * 0.1);
        yield* arrow().end(1, 0.45, easeOutCubic);
      })(),
    ),
  );

  yield* all(
    kernel().opacity(1, 0.4, easeOutCubic),
    kernel().scale(1, 0.5, easeOutCubic),
  );

  yield* waitFor(0.2);

  yield* all(
    outArrow().end(1, 0.45, easeOutCubic),
    outChip().opacity(1, 0.45, easeOutCubic),
  );

  yield* waitFor(1.5);
});
