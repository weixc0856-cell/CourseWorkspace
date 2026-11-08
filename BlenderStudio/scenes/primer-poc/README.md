# Primer-style simulation POC

30 秒验证：Python agent 模拟 → Blender Eevee 六边形世界 → Remotion 三元图/矩阵/排版。

```powershell
# 1. 模拟（确定性，seed=7）
python BlenderStudio/scenes/primer-poc/simulate.py --out build/primer-poc/simulation.json

# 2. Blender 渲染世界（900 帧 PNG，720p）
& $env:BLENDER_EXE -b -P BlenderStudio/scenes/primer-poc/world.py -- `
  --sim build/primer-poc/simulation.json `
  --out build/primer-poc/world/world.mp4

# 3. PNG → MP4
ffmpeg -framerate 30 -start_number 1 -i build/primer-poc/world/frames/frame_%04d.png `
  -c:v libx264 -crf 18 -pix_fmt yuv420p build/primer-poc/world/world.mp4

# 4. Remotion 合成
Copy-Item build/primer-poc/world/world.mp4 RemotionStudio/public/staging/primer-poc/world.mp4
cd RemotionStudio
npx remotion render src/index.ts PrimerPoc ../build/primer-poc/poc.mp4
```

产物：`build/primer-poc/poc.mp4`（1920×1080 / 30fps / 30s）。数据由 `RemotionStudio/src/data/primer-poc.json` 提供。

注意：Blender 5.2 当前构建不支持 `file_format=FFMPEG`，所以先出 PNG 序列再用 ffmpeg 编码。
