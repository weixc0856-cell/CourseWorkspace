import {makeProject} from '@motion-canvas/core';

import attentionFlow from './scenes/01-transformer-demo/attention-flow?scene';
import guiVsCliPaths from './scenes/01-shell-for-ai-era/gui_vs_cli_paths?scene';
import terminalShellLayers from './scenes/01-shell-for-ai-era/terminal_shell_layers?scene';
import argumentTokenization from './scenes/01-shell-for-ai-era/argument_tokenization?scene';
import pathLookupFlow from './scenes/01-shell-for-ai-era/path_lookup_flow?scene';
import unixPipelineStream from './scenes/01-shell-for-ai-era/unix_pipeline_stream?scene';
import redirectionMechanics from './scenes/01-shell-for-ai-era/redirection_mechanics?scene';
import permissionShebang from './scenes/01-shell-for-ai-era/permission_shebang?scene';
import pipelineCaseDemo from './scenes/01-shell-for-ai-era/pipeline_case_demo?scene';

export default makeProject({
  scenes: [
    attentionFlow,
    guiVsCliPaths,
    terminalShellLayers,
    argumentTokenization,
    pathLookupFlow,
    unixPipelineStream,
    redirectionMechanics,
    permissionShebang,
    pipelineCaseDemo,
  ],
});
