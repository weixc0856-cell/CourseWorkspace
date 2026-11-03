import {Circle, Line, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';

import {MK, MK_FONT_MONO, MK_FONT_SANS} from '../../styles/mckinsey';

/**
 * Slide 4 — terminal emulator vs. shell interpreter.
 *
 * 场景按 1280×720 编排；项目画布是 1920×1080，所以整体放大 1.5 倍填满画面。
 * 时长约 10 秒。
 */
export default makeScene2D(function* (view) {
  view.fill(MK.white);
  view.scale(1.5);

  const containerRef = createRef<Rect>();
  const shellBoxRef = createRef<Rect>();
  const kernelBoxRef = createRef<Rect>();
  const arrow1 = createRef<Line>();

  view.add(
    <>
      <Txt
        text={'SYSTEM STACK: EMULATOR VS. INTERPRETER'}
        fontFamily={MK_FONT_SANS}
        fontSize={22}
        fontWeight={700}
        fill={MK.muted}
        letterSpacing={2}
        y={-290}
      />

      {/* 外层：Terminal Emulator */}
      <Rect
        ref={containerRef}
        x={0}
        y={-40}
        width={780}
        height={380}
        radius={12}
        fill={MK.codeBg}
        stroke={MK.border}
        lineWidth={2}
        opacity={0}
      >
        <Circle x={-360} y={-165} size={12} fill={MK.muted} />
        <Circle x={-340} y={-165} size={12} fill={MK.muted} />
        <Circle x={-320} y={-165} size={12} fill={MK.muted} />
        <Txt
          text={'Terminal Emulator (e.g. Alacritty, iTerm2, macOS Terminal)'}
          x={-40}
          y={-165}
          fontFamily={MK_FONT_SANS}
          fontSize={14}
          fill={MK.muted}
        />
        <Txt
          text={'Handles UI, Keyboard Input, Clipboard & Font Rendering'}
          x={180}
          y={150}
          fontFamily={MK_FONT_SANS}
          fontSize={13}
          fill={MK.muted}
        />

        {/* 内层：Shell 进程 */}
        <Rect
          ref={shellBoxRef}
          x={0}
          y={-10}
          width={560}
          height={140}
          radius={8}
          fill={MK.white}
          stroke={MK.border}
          lineWidth={2}
          opacity={0}
        >
          <Txt
            text={'Shell Interpreter (Bash / Zsh)'}
            y={-25}
            fontFamily={MK_FONT_MONO}
            fontSize={22}
            fontWeight={700}
            fill={MK.text}
          />
          <Txt
            text={'Parses Syntax · Resolves $PATH · Dispatches Processes'}
            y={20}
            fontFamily={MK_FONT_SANS}
            fontSize={15}
            fill={MK.muted}
          />
        </Rect>
      </Rect>

      {/* 底层：OS Kernel */}
      <Rect
        ref={kernelBoxRef}
        x={0}
        y={230}
        width={780}
        height={80}
        radius={8}
        fill={MK.text}
        opacity={0}
      >
        <Txt
          text={'Operating System Kernel (Process execution, File system, I/O)'}
          y={0}
          fontFamily={MK_FONT_SANS}
          fontSize={16}
          fontWeight={600}
          fill={MK.white}
        />
      </Rect>

      {/* Shell → Kernel 的系统调用 */}
      <Line
        ref={arrow1}
        points={[
          [0, 20],
          [0, 170],
        ]}
        stroke={MK.orange}
        lineWidth={3}
        endArrow
        arrowSize={8}
        opacity={0}
      />
    </>,
  );

  // ---------- 时序 ----------
  containerRef().scale(0.98);
  yield* all(
    containerRef().opacity(1, 0.7),
    containerRef().scale(1.0, 0.7),
  );
  yield* waitFor(2.0);

  yield* all(
    shellBoxRef().opacity(1, 0.6),
    shellBoxRef().stroke(MK.orange, 0.6),
  );
  yield* waitFor(1.5);

  yield* all(
    kernelBoxRef().opacity(1, 0.6),
    kernelBoxRef().y(210, 0.6),
    arrow1().opacity(1, 0.6),
  );
  yield* waitFor(1.5);

  yield* shellBoxRef().scale(1.03, 0.3);
  yield* shellBoxRef().scale(1.0, 0.3);
  yield* waitFor(2.5);
});
