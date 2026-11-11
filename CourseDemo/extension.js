const vscode = require('vscode');
const fs = require('fs');
const path = require('path');

function env(name) {
  return process.env[name];
}

function writeResult(resultPath, payload) {
  fs.mkdirSync(path.dirname(resultPath), {recursive: true});
  fs.writeFileSync(resultPath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function waitForShellIntegration(terminal, timeoutMs) {
  return new Promise((resolve) => {
    if (terminal.shellIntegration) {
      resolve(terminal.shellIntegration);
      return;
    }
    const timer = setTimeout(() => {
      disposable.dispose();
      resolve(terminal.shellIntegration || null);
    }, timeoutMs);
    const disposable = vscode.window.onDidChangeTerminalShellIntegration((event) => {
      if (event.terminal === terminal) {
        clearTimeout(timer);
        disposable.dispose();
        resolve(event.shellIntegration);
      }
    });
  });
}

function waitForExit(execution, timeoutMs) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (value) => {
      if (finished) return;
      finished = true;
      disposable.dispose();
      clearTimeout(timer);
      resolve(value);
    };
    const disposable = vscode.window.onDidEndTerminalShellExecution((event) => {
      if (event.execution === execution) {
        finish(event.exitCode);
      }
    });
    const timer = setTimeout(() => finish(undefined), timeoutMs);
  });
}

async function runSession(sessionPath, resultPath) {
  const raw = fs.readFileSync(sessionPath, 'utf8').replace(/^﻿/, '');
  const session = JSON.parse(raw);
  const terminal = vscode.window.createTerminal({
    name: 'Course Demo',
    cwd: session.cwd || undefined,
    shellPath: session.shellPath || undefined,
    shellArgs: session.shellArgs || [],
    env: session.env || undefined,
    location: vscode.TerminalLocation.Editor,
  });
  terminal.show();
  await vscode.commands.executeCommand('workbench.action.closeSidebar');
  await vscode.commands.executeCommand('workbench.action.closeAuxiliaryBar');
  terminal.sendText("export PS1='demo@lab:~$ '", true);
  terminal.sendText('clear', true);
  await new Promise((resolve) => setTimeout(resolve, 900));
  const readyPath = env('COURSE_DEMO_READY');
  if (readyPath) {
    const deadline = Date.now() + 30000;
    while (!fs.existsSync(readyPath) && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  const startDelay = Number(session.startDelayMs || 0);
  if (startDelay > 0) {
    await new Promise((resolve) => setTimeout(resolve, startDelay));
  }

  const shell = await waitForShellIntegration(terminal, 15000);
  if (!shell) {
    writeResult(resultPath, {
      ok: false,
      error: 'shell_integration_unavailable',
      commands: [],
    });
    return;
  }

  const results = [];
  for (const command of session.commands) {
    const pause = Number(command.pauseBeforeMs || 0);
    if (pause > 0) {
      await new Promise((resolve) => setTimeout(resolve, pause));
    }
    let output = '';
    let exitCode = null;
    let error = null;
    try {
      const execution = shell.executeCommand(command.command);
      const reader = (async () => {
        for await (const chunk of execution.read()) {
          output += chunk;
        }
      })();
      try {
        exitCode = await waitForExit(execution, 30000);
        if (exitCode === undefined && execution.exitCode) {
          exitCode = await execution.exitCode;
        }
      } catch (exc) {
        error = String(exc);
      }
      await reader;
    } catch (exc) {
      error = String(exc);
    }
    results.push({
      id: command.id,
      command: command.command,
      exit_code: exitCode,
      output,
      error,
    });
  }

  const hold = Number(session.holdAfterMs || 0);
  if (hold > 0) {
    await new Promise((resolve) => setTimeout(resolve, hold));
  }

  writeResult(resultPath, {
    ok: results.every((item) => item.exit_code === 0 && !item.error),
    shell_integration: true,
    commands: results,
  });
}

function activate(context) {
  const sessionPath = env('COURSE_DEMO_SESSION');
  const resultPath = env('COURSE_DEMO_RESULT');
  if (!sessionPath || !resultPath) {
    return;
  }
  runSession(sessionPath, resultPath).catch((error) => {
    writeResult(resultPath, {
      ok: false,
      error: String(error && error.stack ? error.stack : error),
      commands: [],
    });
  });
}

function deactivate() {}

module.exports = {activate, deactivate};
