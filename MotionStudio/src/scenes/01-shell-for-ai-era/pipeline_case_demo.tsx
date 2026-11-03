import {Node, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, sequence, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 19 — end-to-end access-log pipeline.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍。
 * 时长约 15 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const step1 = createRef<Rect>();
  const step2 = createRef<Rect>();
  const step3 = createRef<Rect>();
  const step4 = createRef<Rect>();
  const step5 = createRef<Rect>();

  view.add(
    <Node>
      <Txt
        text={'END-TO-END PIPELINE: LOG PURIFICATION FLOW'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-280}
      />

      {/* 阶段 1: 原始日志 */}
      <Rect
        ref={step1}
        x={-440}
        y={0}
        width={180}
        height={220}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'cat'}
          y={-70}
          fontFamily={MK_FONT_MONO}
          fontSize={18}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'10,000 Rows'}
          y={-20}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
        />
        <Txt
          text={'Raw HTTP Logs'}
          y={20}
          fontFamily={MK_FONT_SANS}
          fontSize={12}
          fill={MK.muted}
        />
      </Rect>

      {/* 阶段 2: 过滤 403 */}
      <Rect
        ref={step2}
        x={-220}
        y={0}
        width={180}
        height={180}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'grep 403'}
          y={-50}
          fontFamily={MK_FONT_MONO}
          fontSize={18}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'320 Rows'}
          y={0}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
        />
        <Txt
          text={'Filter Blocked'}
          y={40}
          fontFamily={MK_FONT_SANS}
          fontSize={12}
          fill={MK.muted}
        />
      </Rect>

      {/* 阶段 3: 提取 IP */}
      <Rect
        ref={step3}
        x={0}
        y={0}
        width={180}
        height={150}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={"awk '{print $1}'"}
          y={-40}
          fontFamily={MK_FONT_MONO}
          fontSize={16}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'320 IPs'}
          y={5}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
        />
        <Txt
          text={'Column Strip'}
          y={40}
          fontFamily={MK_FONT_SANS}
          fontSize={12}
          fill={MK.muted}
        />
      </Rect>

      {/* 阶段 4: 排序去重聚合 */}
      <Rect
        ref={step4}
        x={220}
        y={0}
        width={180}
        height={130}
        radius={8}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'uniq -c'}
          y={-30}
          fontFamily={MK_FONT_MONO}
          fontSize={17}
          fontWeight={700}
          fill={MK.text}
        />
        <Txt
          text={'12 Unique'}
          y={10}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fontWeight={600}
          fill={MK.orange}
        />
        <Txt
          text={'after sort · sort -nr'}
          y={40}
          fontFamily={MK_FONT_SANS}
          fontSize={12}
          fill={MK.muted}
        />
      </Rect>

      {/* 阶段 5: Top 5 输出 */}
      <Rect
        ref={step5}
        x={440}
        y={0}
        width={180}
        height={110}
        radius={8}
        fill={MK.orangeSoft}
        stroke={MK.orange}
        lineWidth={2}
        opacity={0}
      >
        <Txt
          text={'head -n 5'}
          y={-25}
          fontFamily={MK_FONT_MONO}
          fontSize={18}
          fontWeight={700}
          fill={MK.orange}
        />
        <Txt
          text={'Top 5 Attackers'}
          y={15}
          fontFamily={MK_FONT_SANS}
          fontSize={13}
          fontWeight={600}
          fill={MK.text}
        />
      </Rect>
    </Node>,
  );

  // ---------- 时序 ----------
  yield* waitFor(1.0);

  yield* sequence(
    0.3,
    all(step1().opacity(1, 0.5), step1().y(-10, 0.5)),
    all(step2().opacity(1, 0.5), step2().y(-10, 0.5)),
    all(step3().opacity(1, 0.5), step3().y(-10, 0.5)),
    all(step4().opacity(1, 0.5), step4().y(-10, 0.5)),
    all(step5().opacity(1, 0.5), step5().y(-10, 0.5)),
  );
  yield* waitFor(4.0);

  yield* step5().scale(1.08, 0.3);
  yield* step5().scale(1.0, 0.3);
  yield* waitFor(5.7);
});
