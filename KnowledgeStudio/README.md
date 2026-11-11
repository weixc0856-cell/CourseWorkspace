# KnowledgeStudio


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个领域方案；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
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

# 6. 按主题取页（默认最多 18 页），可直接写成 lesson 的 sources 片段
uv run --project KnowledgeStudio knowledge-studio retrieve --root knowledge/hucho `
    --query "drag mechanisms" --max-pages 18 --into-lesson lessons/02-car-aerodynamics

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

- `knowledge/` 只在本机：教材通常受版权保护，原件与拆页不进仓库。
- 规则：只读检索到的页；引用到页并带页哈希；claim 的 `verification` 由人工确认，工具从不自动标 `verified`。
- 检索是确定性的词法匹配（SQLite FTS5），不引入向量库；需要语义检索时作为补充，不替换页级事实。

- `extract-report` 只读：fatal 必须为 0 才允许建索引；`--allow-empty` 是唯一允许空页的出口，必须逐页声明。

完整规范：[docs/KnowledgeStudio.md](../docs/KnowledgeStudio.md)
