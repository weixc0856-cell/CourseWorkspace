# Bundled font: Noto Sans SC

- **Family**: Noto Sans SC — Latin 400 / 600 / 700, Simplified Chinese 400
- **Source**: [`@fontsource/noto-sans-sc@5.3.1`](https://www.npmjs.com/package/@fontsource/noto-sans-sc), which redistributes Google's Noto Sans SC
- **Files**: Latin subsets (`noto-sans-sc-latin-{400,600,700}-normal.woff2`, 13 KB each) and the Simplified Chinese subset (`noto-sans-sc-chinese-simplified-400-normal.woff2`, 1.1 MB)
- **License**: SIL Open Font License 1.1 — free for commercial use, embedding and redistribution; see `LICENSE-NotoSansSC.txt`
- **Why**: Remotion previously relied on the operating system's font stack, so Chinese glyphs and Latin metrics varied by machine. Bundling one OFL font makes 2D captions and annotations reproducible offline.
- **Scope**: Remotion only. Blender TEXT keeps using its built-in Bfont and does not load external font files.
- **Weight**: Latin 400/600/700 and CJK 400. Brand frames are English-only (D-065), so no CJK bold face is bundled; captions and course content keep using CJK 400.
