import {
  Color,
  MetaFile,
  ObjectMetaField,
  Renderer,
  Vector2,
  bootstrap,
  makePlugin,
} from '@motion-canvas/core';

import attentionFlow from './scenes/01-transformer-demo/attention-flow?scene';
import guiVsCliPaths from './scenes/01-shell-for-ai-era/gui_vs_cli_paths?scene';
import terminalShellLayers from './scenes/01-shell-for-ai-era/terminal_shell_layers?scene';
import argumentTokenization from './scenes/01-shell-for-ai-era/argument_tokenization?scene';
import pathLookupFlow from './scenes/01-shell-for-ai-era/path_lookup_flow?scene';
import unixPipelineStream from './scenes/01-shell-for-ai-era/unix_pipeline_stream?scene';
import redirectionMechanics from './scenes/01-shell-for-ai-era/redirection_mechanics?scene';
import permissionShebang from './scenes/01-shell-for-ai-era/permission_shebang?scene';
import pipelineCaseDemo from './scenes/01-shell-for-ai-era/pipeline_case_demo?scene';

const scenes = {
  'attention-flow': attentionFlow,
  'gui-vs-cli-paths': guiVsCliPaths,
  'terminal-shell-layers': terminalShellLayers,
  'argument-tokenization': argumentTokenization,
  'path-lookup-flow': pathLookupFlow,
  'unix-pipeline-stream': unixPipelineStream,
  'redirection-mechanics': redirectionMechanics,
  'permission-shebang': permissionShebang,
  'pipeline-case-demo': pipelineCaseDemo,
};

const params = new URLSearchParams(window.location.search);
const sceneName = params.get('scene') || 'attention-flow';
const scene = scenes[sceneName];
const sink = params.get('sink') || 'http://127.0.0.1:4174';
const fps = Number(params.get('fps') || 30);
const width = Number(params.get('width') || 1920);
const height = Number(params.get('height') || 1080);
const failAt = Number(params.get('failAt') || 0);
const status = document.getElementById('status');

const setStatus = (text) => {
  status.textContent = text;
  window.__RENDER_STATUS__ = text;
};

class HeadlessExporter {
  static id = 'headless-frame-sink';
  static displayName = 'Headless frame sink';

  static meta() {
    return new ObjectMetaField('Headless', {});
  }

  static async create(_project, settings) {
    return new HeadlessExporter(settings);
  }

  constructor(settings) {
    this.settings = settings;
  }

  async request(pathname, body, contentType = 'application/json') {
    const response = await fetch(`${sink}${pathname}`, {
      method: 'POST',
      headers: { 'Content-Type': contentType },
      body,
    });
    if (!response.ok) {
      throw new Error(`${pathname} failed: ${response.status} ${await response.text()}`);
    }
    return response;
  }

  async start() {
    await this.request('/start', JSON.stringify({
      scene: sceneName,
      fps,
      width,
      height,
      range: this.settings.range,
      exportedAt: new Date().toISOString(),
    }));
  }

  async handleFrame(canvas, frame) {
    if (failAt > 0 && frame >= failAt) {
      throw new Error(`injected failure at frame ${frame}`);
    }
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error(`could not encode frame ${frame}`);
    await this.request(`/frame?frame=${frame}`, blob, 'image/png');
    if (frame % fps === 0) setStatus(`rendering frame ${frame}`);
  }

  async stop(result) {
    await this.request(`/stop?result=${result}`, JSON.stringify({result}));
  }
}

const plugin = makePlugin({
  name: 'courseworkspace-headless',
  exporters: () => [HeadlessExporter],
})();

const main = async () => {
  if (!scene) {
    throw new Error(`unknown scene: ${sceneName}`);
  }

  const project = bootstrap(
    'courseworkspace-headless',
    { core: '3.17.2', two: '3.17.2', ui: null, vitePlugin: '3.17.2' },
    [plugin],
    { scenes: [scene] },
    new MetaFile('headless.meta', false),
    new MetaFile('headless.settings', false),
  );
  project.meta.shared.size.set(new Vector2(width, height));
  project.meta.shared.background.set(new Color('#FBFAF7'));

  const renderer = new Renderer(project);
  const finished = new Promise((resolve) => renderer.onFinished.subscribe(resolve));

  setStatus('starting renderer');
  renderer.render({
    name: sceneName,
    range: [0, 1e9],
    fps,
    size: new Vector2(width, height),
    resolutionScale: 1,
    colorSpace: 'srgb',
    background: '#FBFAF7',
    exporter: { name: HeadlessExporter.id, options: {} },
  });

  const result = await finished;
  const label = result === 0 ? 'success' : result === 2 ? 'aborted' : 'error';
  setStatus(`finished: ${label}`);
  window.__RENDER_RESULT__ = label;
  window.__RENDER_ERRORS__ = [];
  window.__RENDER_DONE__ = true;
};

main().catch((error) => {
  setStatus(`failed: ${error.message}`);
  window.__RENDER_RESULT__ = 'error';
  window.__RENDER_ERRORS__ = [String(error.stack || error)];
  window.__RENDER_DONE__ = true;
});
