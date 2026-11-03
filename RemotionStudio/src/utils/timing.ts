export const secondsToFrames = (seconds: number, fps: number): number =>
  Math.max(0, Math.round(seconds * fps));

export const stagingPath = (lesson: string, source: string): string =>
  `staging/${lesson}/${source}`;

export interface Cue {
  start: number;
  end: number;
  text: string;
}

const toSeconds = (value: string): number => {
  const match = value.trim().match(/^(\d+):(\d{2}):(\d{2})[,.](\d{3})$/);
  if (!match) {
    throw new Error(`invalid SRT timestamp: ${value}`);
  }
  const [, hours, minutes, seconds, millis] = match;
  return (
    Number(hours) * 3600 +
    Number(minutes) * 60 +
    Number(seconds) +
    Number(millis) / 1000
  );
};

export const parseSrt = (input: string): Cue[] => {
  const blocks = input.replace(/\r\n/g, '\n').trim().split(/\n{2,}/);
  const cues: Cue[] = [];
  for (const block of blocks) {
    const lines = block.split('\n');
    if (lines.length < 2) continue;
    const timeLine = lines.find((line) => line.includes('-->'));
    if (!timeLine) continue;
    const [startRaw, endRaw] = timeLine.split('-->');
    const text = lines
      .slice(lines.indexOf(timeLine) + 1)
      .join('\n')
      .trim();
    if (!text) continue;
    cues.push({start: toSeconds(startRaw), end: toSeconds(endRaw), text});
  }
  return cues.sort((a, b) => a.start - b.start);
};
