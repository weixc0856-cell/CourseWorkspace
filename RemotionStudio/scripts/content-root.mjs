// Resolve the course content root for scripts that read or write media.
//
// Order: COURSEWORKSPACE_CONTENT_ROOT -> config/local-paths.yaml: content_root.
// There is no fallback to the workspace: media written next to the code is the
// failure this module exists to prevent. Callers get a throw, not a quiet path.

import { existsSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const workspace = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

export function contentRoot(env = process.env) {
  const configured = env.COURSEWORKSPACE_CONTENT_ROOT;
  if (configured) {
    return resolve(configured);
  }
  const config = resolve(workspace, 'config', 'local-paths.yaml');
  if (!existsSync(config)) {
    throw new Error('content root not configured: set COURSEWORKSPACE_CONTENT_ROOT or config/local-paths.yaml');
  }
  const match = /^content_root:\s*["']?([^"'\n#]+?)["']?\s*$/m.exec(readFileSync(config, 'utf8'));
  if (!match) {
    throw new Error('content root not configured: config/local-paths.yaml has no content_root key');
  }
  const value = match[1].trim();
  const root = isAbsolute(value) ? resolve(value) : resolve(workspace, value);
  if (root === workspace) {
    throw new Error('content root resolves to the workspace; media must not be written into the repo');
  }
  return root;
}

export function contentPath(...parts) {
  return resolve(contentRoot(), ...parts);
}
