import {makeProject} from '@motion-canvas/core';

import {scenes} from './scenes.generated';

// The scene list is generated from src/scenes by scripts/sync-scenes.mjs, so a
// new scene only needs to appear in a directory.
export default makeProject({
  scenes: Object.values(scenes),
});
