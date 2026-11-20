# KnowledgeStudio


教材与知识资产管理：把一本专业教材拆成**按页可引用**的知识单元，让一节课只读它需要的十几页。

教材、论文与视频来源统一进入本机 Docling 资料区；采集与预处理见 [docs/资料采集与预处理.md](../docs/资料采集与预处理.md)。PDF 的 `document.md` / `pages/` 与 YouTube 的 `transcript.clean.md` 都从该区读取。

```powershell
uv sync --project KnowledgeStudio

# 1. 导入（PDF 或已提取文本）
uv run --project KnowledgeStudio knowledge-studio import-source `
    --pdf <book>.pdf --source-id hucho --root knowledge/hucho --title "Aerodynamics of Road Vehicles"
uv run --project KnowledgeStudio knowledge-studio import-text `
    --text book.txt --source-id hucho --root knowledge/hucho

# 2. 目录 + 印刷页→PDF 页校准
uv run --project KnowledgeStudio knowledge-studio toc --root knowledge/hucho

# 3. 按章切单元 → 4. 建索引
uv run --project KnowledgeStudio knowledge-studio segment --root knowledge/hucho
uv run --project KnowledgeStudio knowledge-studio index --root knowledge/hucho

# 5. 提取质检：缺页 / 空页 / 断词 / 替换字符（先跑，再建索引）
uv run --project KnowledgeStudio knowledge-studio extract-report `
    --root knowledge/hucho --min-chars 200 --allow-empty 12,13-15

# 6. 按主题取页（默认最多 18 页）；--pages 限定 PDF 页范围，--full-pages 保留整页标题，--register 直接写入 lesson 的 sources.yaml
uv run --project KnowledgeStudio knowledge-studio retrieve --root knowledge/hucho `
    --query "scope and character of vehicle aerodynamics" `
    --pages 22-27 --max-pages 6 --full-pages `
    --into-lesson lessons/<slug> --entry-id S1 --register

> `retrieve` 的约定（2026-11-18）：`--pages N-M` 先收窄候选页，避免拉到其他章节/索引页；`--full-pages` 写整页而不是 700 字窗口，保证 `1.1.2` 这类标题不丢；`--register` 把条目追加/替换进 `authoring/sources.yaml`（只写片段时由人合并）。条目 sha256 用解码后的文本计算，与 `course-control digest` 一致；源标记只在真正知道印刷页时写 `printed=`，否则只写 `pdf=`。

# 7. claim → 页 的证据
uv run --project KnowledgeStudio knowledge-studio evidence --root knowledge/hucho `
    --retrieval knowledge/hucho/retrieval/<id>.json --claims claims.json

# 8. 结构校验：引用页哈希、quote 是否在页上、数字是否出现（不判断真伪）
uv run --project KnowledgeStudio knowledge-studio span-check --root knowledge/hucho `
    --evidence knowledge/hucho/evidence/<id>.evidence.json

# 9. 书图：章节 / PDF 页范围 / 单元 / 图表计数
uv run --project KnowledgeStudio knowledge-studio map --root knowledge/hucho

# 10. 完整性检查
uv run --project KnowledgeStudio knowledge-studio verify --root knowledge/hucho
```
# 11. 概念层与课程规划（2026-11-13）

```powershell
uv run --project KnowledgeStudio knowledge-studio knowledge-ir-validate `
    --file knowledge-ir.yaml
uv run --project KnowledgeStudio knowledge-studio curriculum-validate `
    --plan curriculum.yaml --knowledge knowledge-ir.yaml --min-lessons 30 --max-lessons 50
uv run --project KnowledgeStudio knowledge-studio schemas --output shared/schemas
```

- `knowledge-ir`：概念/先修/claim/证据/冲突；`supported` 需两个独立页或一条 derivation，`contested_resolved` 需写采用理由。
- `curriculum`：覆盖、先修顺序、集数窗口；豁免必须写明理由。
- 这些检查判断"证据是否足够携带主张"，不判断主张真伪；工具不会自动把 claim 升级为 `supported`。


- `knowledge/` 只在本机：教材通常受版权保护，原件与拆页不进仓库。
- 规则：只读检索到的页；引用到页并带页哈希；claim 的 `verification` 由人工确认，工具从不自动标 `verified`。
- 检索是确定性的词法匹配（SQLite FTS5），不引入向量库；需要语义检索时作为补充，不替换页级事实。

- `extract-report` 只读：fatal 必须为 0 才允许建索引；`--allow-empty` 是唯一允许空页的出口，必须逐页声明。

完整规范：[docs/KnowledgeStudio.md](../docs/KnowledgeStudio.md)
