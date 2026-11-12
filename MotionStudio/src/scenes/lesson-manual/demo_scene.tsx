import {makeScene2D, Txt} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';

// Repository fixture scene: the Motion Canvas adapter test only needs a scene
// file that resolves; it never renders this one.
export default makeScene2D(function* (view) {
  const label = createRef<Txt>();
  view.add(<Txt ref={label} text="lesson-manual fixture" />);
  yield* waitFor(1);
});
