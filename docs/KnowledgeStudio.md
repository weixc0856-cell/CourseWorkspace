# KnowledgeStudio：教材驱动的课程生产

日期：2026-11-09

> 教材、论文与视频来源统一进入本机 Docling 资料区；采集与预处理见 [资料采集与预处理.md](资料采集与预处理.md)。
代码：`KnowledgeStudio/`（`src/knowledge_studio/`）
命令：`knowledge-studio import-source | toc | segment | index | retrieve | evidence | span-check | map | verify | extract-report | status`

## 1. 它解决什么

现有链路解决“有了人工写的课程内容之后，如何稳定产出课件、动画、旁白与成片”。KnowledgeStudio 解决它前面的一步：**把一本几百到一千多页的专业教材，变成可按章节定位、按知识点取页、且每一页都可引用的本地知识库**，让一节课只读它需要的十几页，而不是把整本书塞进一次请求。

它不生成课程内容，也不判断结论真伪。它只做四件事：拆页、建单元、检索取页、留下引用证据。Brief / Outline / Script 仍由现有 authoring 与 Claude Code 后端生成，进入 Director / Producer。

## 2. 四层结构与边界

```text
原作（PDF / 已提取文本）            local_only，不进仓库
      │  import-source / import-text
页（p0001.md …，带页码标记）        pages/ + metadata/page_map.json
      │  extract-report（缺页/空页/断词/替换字符 → qa/extraction.*）
      │  toc（目录 + 印刷页→PDF 页偏移）
单元（按章切分，含图注索引）         units/U01…/unit.yaml + pages_XXX_YYY.md
      │  index（SQLite + FTS5）
检索（一节只读指定页）              retrieval/<query_id>.json/.md
      │  evidence（claim → 页）
证据（可追溯引用，verification=pending）
      │  export（写 lesson 的 sources 片段）
CourseControl：ingest → digest → brief → outline → script → director → producer
```

- **不替换**现有 `authoring/ingest.py` / `digest.py`：导出物是普通 Markdown 源，`digest` 继续按标题切段。
- **不引入向量库与 RAG 框架**：教材有明确目录、章节与页码，第一版用 SQLite + FTS5 + Markdown + JSON 足够，且完全可复现。
- **不写 lesson 的 `sources.yaml`**：导出只写 `authoring/sources/KS-*.md` 与 `authoring/sources.ks-*.yaml` 片段，合并由人或显式步骤决定，避免覆盖作者内容。

## 3. 磁盘布局

```text
knowledge/<source_id>/
  source.yaml                       # SourceMeta（标题、版次、哈希、页数、提取器）
  original/<book>.pdf               # 原件，local_only
  pages/p0001.md …                  # 每页一个文件，首行 <!-- ks:page pdf=1 -->
  metadata/page_map.json            # pdf_page ↔ printed_page ↔ 哈希 ↔ 标题/图注
  metadata/toc.json                 # 目录条目 + 校准偏移 + 方法
  units/U01-<slug>/
    unit.yaml                       # 页码范围、印刷页码、关键词、文件清单
    pages_006_008.md                # 带页标记的单元正文
    figures.json                    # 图 / 表 / 公式编号与图注
  index/knowledge.db                # pages / units / figures / pages_fts / meta
  retrieval/<query_id>.json|.md     # 一次检索的页、摘录、引用与预算
  evidence/<query_id>.evidence.json # claim → citation，verification=pending
  qa/report.json                    # KS-01…KS-08
  qa/extraction.json|md             # 提取质检：fatal / serious / cosmetic 与异常页清单
```

`knowledge/` 已在 `.gitignore`：教材通常受版权保护，原件、拆页与提取文本都只留在本机；课程以自己的讲解与原创图示为主体。

## 4. 数据契约（`models.py`）

| 模型 | 关键字段 | 约束 |
| --- | --- | --- |
| `SourceMeta` | `source_id`、`original_sha256`、`pdf_pages`、`extractor` | `source_id` 为 slug；`local_only` 默认 `true` |
| `PageRecord` | `pdf_page`、`printed_page`、`sha256`、`headings`、`figures` | 哈希按页文本计算，篡改可被 QA 发现 |
| `TocEntry` | `level`、`title`、`printed_page`、`pdf_page` | 目录层级来自编号深度 |
| `UnitMeta` | `pdf_pages`、`printed_pages`、`keywords`、`files` | `1 <= start <= end`，单元不得越界或重叠 |
| `Citation` | `ref`、`pdf_page`、`page_sha256`、`excerpt_sha256` | 引用到页，且记录当页哈希 |
| `RetrievalResult` | `pages_read`、`total_pages`、`citations`、`excerpts` | 只读“需要的页”，不是整本 |
| `ClaimRef` | `claim_id`、`statement`、`citations`、`verification` | 默认 `pending`；工具从不自动标 `verified` |

## 5. 目录与页码校准

`toc` 做三件事：

1. 只在前 12 页（可调）解析“标题 + 引导点 + 页码”的行，避免把正文误判为目录；
2. 用 **页面开头命中（2 分）/ 全文命中（1 分）** 给每个候选偏移打分，取最高分、同分取绝对值更小的偏移；只按“全文出现”打分会把偏移错算一页；
3. 写 `page_map.json`：`printed_page = pdf_page - offset`，前面版权页等返回负值的页保持 `null`。

目录解析失败时回退到章节标题（`Chapter N` / `第 N 章`）建单元，并在 `toc.json` 里把 `method` 记为 `headings` —— 方法写清楚，不把回退当正常。也可以用 `--manual` 提供人工目录。

## 6. 检索：确定性、按页、有预算

```powershell
knowledge-studio retrieve --root knowledge/hucho --query "drag decomposition" --max-pages 18
```

- 查询词：Latin 词 + 中文短语；中文按字拆开建 FTS 短语（`"阻 力"`），否则 unicode61 会把整段中文当成一个 token；
- 评分：FTS5 `bm25`，落在标题/关键词命中的单元内乘 1.35；
- 上下文：命中页的左右各一页按 0.4 倍分进入候选，但**只从候选里按分数取 `max_pages` 页**，不补齐、不凑数；
- 输出：`retrieval/<query_id>.json` 与可读 `.md`；每条摘录带 `ref`（`<source_id>:p<印刷页>`）、PDF 页与页面哈希；
- 无命中或查询无有效词直接报错，返回 0 页不是“成功”。

示例（12 页冒烟教材，真实运行）：查询 `drag coefficient`，`max_pages=4` → 读 4/12 页（33.3%），落在单元 U02；查询 `风洞 实验` → 3/12 页，跨 U02/U03。真实一千页教材的收益是同一机制上的比例放大，而不是示例数字。

## 7. 证据与“不伪造验收”

`evidence` 只接受**本次检索已经读过的页**：

```powershell
knowledge-studio evidence --root knowledge/hucho \
  --retrieval knowledge/hucho/retrieval/drag-coefficient-xxxx.json \
  --claims build/claims.json
```

- claim 引用未检索的页 → 直接失败并列出；
- 每条 claim 至少一条引用；
- 写出 `evidence/<query_id>.evidence.json`，`verification` 固定 `pending`：是否成立由人工与来源负责，工具不替它下结论；
- 课程正文里的每个关键结论都应能落到一条 claim → 一页原文。

### 7.1 `span-check`：只证明"文本在页上"

```powershell
knowledge-studio span-check --root knowledge/hucho `
    --evidence knowledge/hucho/evidence/<query>.evidence.json [--claims claims.json]
```

它做三件事，都是结构检查：

1. 引用页仍然存在，页面哈希与引用记录一致；
2. claim 的可选 `quote` 能在至少一个被引页上找到（大小写、连字符换行、空白做归一化）；
3. claim 语句里的数字能在被引页上找到（缺数字默认 warning，`--strict-numbers` 改为 blocking）。

它**不判断** quote 是否支持 claim，也不把 `verification` 改成 `verified`。输出 `evidence/<query>.spancheck.json|md`；blocked 退出 1，warn/pass 退出 0。

真实教材试点（352 页）第一次运行就抓到一个"看起来对、实际不连续"的引用：页面版面把侧栏文字插进了正文，quote 少了首词就无法在归一化文本中命中。修正 quote 后 5/5 pass。这正是它该做的事。

### 7.2 `map`：确定性的书图

```powershell
knowledge-studio map --root knowledge/hucho
```

输出 `map/book-map.json|md`：一级章节、PDF 页范围、覆盖单元、图/表/公式计数、单元关键词。它只索引"书里有什么、在哪里"，不生成概念图，也不判断哪些内容值得讲。概念选择写在领域方案里；具体课程方案留在本机 `runtime/course-content/`，不进仓库。

## 8. 接入 CourseControl

```powershell
knowledge-studio retrieve --root knowledge/hucho --query "drag mechanisms" \
  --max-pages 18 --into-lesson lessons/02-car-aerodynamics
```

导出两个文件：

- `authoring/sources/KS-<source>-<query>.md`：按单元 `##` 分节、逐页 `<!-- ks:page pdf=N printed=M -->` 标记，`digest` 可直接按标题切段；
- `authoring/sources.ks-<source>.yaml`：一条符合 `SourceEntry` 的 `sources` 片段（下一个空闲 `S<n>`、SHA-256、`extractor: knowledge-studio`）。

把它合并进 `authoring/sources.yaml` 后，`course-control digest` 会生成带 `ref` 的分段摘要，后续 `brief / outline / script` 只看到这些页——教材定位与引用发生在进入 LLM 之前，而不是让模型“记得整本书”。

## 9. QA（`verify` 与 `extract-report`）

| 编号 | 检查 |
| --- | --- |
| KS-01 | `source.yaml` 可读，原件存在且哈希一致 |
| KS-02 | 页文件数 = `pdf_pages` |
| KS-03 | `page_map` 覆盖全部页，逐页哈希一致（篡改即 blocked） |
| KS-04 | 目录条目都落在页范围内 |
| KS-05 | 单元连续、不重叠、不越界，页标记覆盖声明的页码范围 |
| KS-06 | 索引存在且与当前页/单元一致（防 stale index） |
| KS-07 | 每条引用指向存在的页，页面哈希未变，每条摘录都被引用 |
| KS-08 | 每条 claim 至少一条引用，且引用出自检索池 |

任何一项 blocked 都返回 exit 1；不写 `pass`。

### 9.1 提取质检（`extract-report`）

`verify` 证明页在、哈希没变；它不证明每页真的抽到了字。空页、断词、替换字符都会带着合法哈希通过。`extract-report` 补这一层，只读，不重写 pages / units / index：

```powershell
uv run --project KnowledgeStudio knowledge-studio extract-report `
    --root knowledge/hucho --min-chars 200 --allow-empty 12,13-15
```

| 级别 | 包含 | 处理 |
| --- | --- | --- |
| fatal | 页文件缺失、提取为空的页（未被 `--allow-empty` 声明） | 修好才允许 `index` |
| serious | 断词行、U+FFFD、控制字符、`page_map` 缺页或页码倒退、目录条目在当页找不到 | 逐条打开确认，修不了就记“该页不可引用” |
| cosmetic | 短页（图版/章节扉页）、超长页、未换行长行、重复页眉页脚、单元外页 | 只报告，建索引时降权 |

验收口径：**fatal = 0**；serious 每条有处理记录；页数、目录条目数、单元覆盖三者在报告里一致。输出 `qa/extraction.json`（完整）与 `qa/extraction.md`（人工过目），exit 1 表示存在 fatal。

`--allow-empty` 是唯一允许空页的方式，必须逐页显式声明——版权页、空白页、纯图版要写清楚，不允许“空页默认通过”。

## 10. 已知边界

- 扫描版 PDF 需要先 OCR：`import-text` 接受 `\f` 分页或 `<!-- ks:page pdf=N -->` 标记的文本，本模块不含 OCR。
- 表格与公式只做**图注级**索引（编号 + 标题 + 页），没有单元格结构和公式语义；公式排版仍走 `docs/公式排版规范.md`。
- 图注识别是规则匹配（`Fig.` / `Figure` / `Table` / `Eq.`），非英文教材需要先扩规则或人工 `figures.json`。
- 检索是词法匹配，不做同义词/跨语言扩展；需要语义检索时，等 R1/R2 稳定后再作为补充，而不是替换页级事实。
- 单元按一级目录切分；一本书若一级目录下没有二级结构，单元会较大，可先人工提供 `metadata/toc.json`。
- `evidence` 与 `span-check` 只做“引用可追溯 + 文本/数字在场”，不做 claim 真伪判断，也不校验模型生成的表述是否被原文支持——那需要人工或独立审查。quote 不在页上会 blocked；quote 在页上不代表结论成立。
- `extract-report` 只能检查文本层，不能判断阅读顺序：pypdf 不提供坐标，双栏是否串行无法验证；需要这条能力时，换带 bbox 的抽取器（如 PyMuPDF）并补一条基于块的检查。
- 图注仍是规则匹配；`extract-report` 不校验“图注是否跟在图后面”。

## 11. 依赖

新增 `pypdf==6.9.2`（BSD-3-Clause，10,291 star / 1,695 fork / 155 open issues，最近 push 2026-11-09；7.0.0 于 2026-11-06 发布，过于新，暂不升级）。登记见 `docs/第三方依赖准入规范.md`。其余依赖（pydantic / PyYAML / typer）与现有工程一致；SQLite FTS5 是 Python 标准库自带能力（本机 SQLite 3.49.1）。

## 12. 已验证

- `KnowledgeStudio` 单测 27 个（`extract-report` 8 个、`span-check` 5 个、`map` 1 个；其余为页切分/目录/单元/检索/证据）：页切分、标记校验、pypdf 真实解析、目录解析与偏移校准（-4 页）、单元范围、英文/中文检索、页预算、检索落盘与 QA、claim 只能引用已检索页、导出片段、篡改页哈希后 QA blocked、无目录时回退章节标题。
- CLI 真实运行（`build/knowledge-smoke/`）：PDF 导入 2 页（`pypdf==6.9.2`）、文本教材 12 页 → 目录 4 条、偏移 -4 → 3 个单元 → 检索 `drag coefficient` 4/12 页、`风洞 实验` 3/12 页 → 两条 claim 证据 → `verify` KS-01…KS-08 全 pass。
- `extract-report` 真实运行（`build/knowledge-smoke/pdf-book`）：2/2 页，status pass，短页 2 条为 cosmetic，TOC 缺失如实记入报告。
- 真实教材试点（2026-11-10）：一本 352 页英文教材经 Docling 转成 352 页资料包，`to-knowledge` 用 PDF 书签建 18 个单元，`verify` KS-01…KS-08 pass；`map` 输出 18 章；5 条教材 claim 经 `evidence` + `span-check` 5/5 pass。
- `scripts/check.ps1` 已包含 KnowledgeStudio 单测。
