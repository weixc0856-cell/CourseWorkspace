# 资产治理（ASSET_GOVERNANCE）

- 日期：2026-11-10
- 关联：C-11、C-17、C-21、C-30
- 实现：`assets.py`、`package.py`、`vendor.py`、`scripts/check_evidence.py`

## 1. 资产寻址

每个生产资产必须能被描述成：

```json
{
  "asset_id": "bgm:schubert_d664_piano.wav",
  "path": "<bgm_root>/commons/schubert_d664_piano.wav",
  "origin": "bgm",
  "exists": true,
  "sha256": "…",
  "license_status": "public_domain",
  "attribution": "Schubert D.664, public domain"
}
```

- `origin`：`workspace` / `bgm` / `ai` / `tts-runtime` / `voice-ref` / `external`。
- 工作区内资产用 `workspace:<相对路径>`；受控根目录用 `<root>:<相对路径>`。
- 绝对路径只作为本机映射，不作为权威。换机时由 `config/local-paths.yaml` 重新映射。
- `audio/mix.json` 增加 `source_asset`；`source_track` 保留用于兼容。

根目录来自 `config/local-paths.yaml`：`bgm_root`、`ai_root`、`tts.runtime_dir`。

## 2. 交付包必须自包含

`course-control package` 除了复制母版、字幕、报告，还会：

1. 从 `audio/mix.json` 与 `narration/narration.meta.json` 收集外部资产；
2. 复制到 `package/assets/external/<hash>-<name>`；
3. 在 `manifest.json.external_assets[]` 记录原始路径、`asset_id`、SHA-256、许可与归属；
4. `package-verify` 重新哈希这些文件。

外部资产丢失时 package 失败，而不是生成一个"本机能播、换机就丢"的包。

## 3. 证据引用

`docs/` 中引用的 `build/...` 路径由 `scripts/check_evidence.py` 审计：

- 存在的路径：正常。
- 缺失的路径：必须匹配 `docs/audit/evidence-decisions.yaml` 的规则。
- 未分类的缺失路径：检查失败。

处置值：

| 处置 | 含义 |
| --- | --- |
| `retained` | 仍需要的证据，必须恢复 |
| `regenerable` | 有文档命令可重新生成 |
| `retired_poc` | 已退出生产路径的实验 |
| `historical` | 归档/历史记录，不要求存在 |
| `stale_ref` | 文档写错，应修文档 |
| `external` | 工作区外生成 |

2026-11-10 结果：引用 182，缺失 90，全部有处置，未分类 0。报告写入 `build/.audit/missing-evidence.txt` 与 `evidence-classification.json`。

## 4. 第三方运行时

- `CodeVideoStudio/vendor/three/three.module.js` 是唯一 checked-in 副本（r160，MIT）。
- 每个镜头目录里的 `three.module.js` 是构建输入：`course-control vendor-sync` 或 `render:code_video` 自动复制，`.gitignore` 排除。
- `course-control vendor-check` 发现副本缺失或哈希不一致即失败；`check.ps1` 已包含。
- 升级：替换 vendor 文件 → `vendor-sync` → 重捕获使用它的镜头 → 更新 `VERIFY.md`。

## 5. 不变量

- 不把 `lessons/`、`build/`、`runtime/`、模型权重、媒体文件提交到远程仓库。
- 不删除未知来源的用户资产；无法确认的路径标记为 `OPEN`，不猜。
- 不在交付包里放绝对路径作为唯一索引；相对路径与哈希是复核依据。
- 写入报告、清单、检查点使用原子写，避免中断留下半个文件。
