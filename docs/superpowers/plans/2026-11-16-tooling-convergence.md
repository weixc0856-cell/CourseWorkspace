# 工具链收敛计划 · 2026-11-16

- **状态**：计划。**尚未执行任何代码改动。**
- **基线**：`f18d2678bf05b81e9e0756efa1f887bf13a5ec2`（分支 `handoff/2026-11-16-docs-and-layout`，工作区干净）。
- **范围**：只解决工具链与验收契约。不改课程内容、证据资产、`deliver/` 产物；不 push、不 reset、不重写历史。
- **拆分**：A 文档治理 · B 内容根与 build 布局 · C 课程就绪与发布证据。三块可独立验收。

> **读法**：先看 §0 与 §4 的追踪表；要开工只看对应子项目的 §3.x 与 §5 的任务卡。

---

## 0. 一页结论

| 项 | 结论 |
| --- | --- |
| 最新评审 4 条 P1 | 全部 **fix**，全部有可复现的失败证据（§1） |
| 最新评审 4 条 P2 | 全部 **fix**，无 defer |
| 子项目 | A（文档治理）· B（内容根与 build 布局）· C（课程就绪与发布证据） |
| 任务数 | 21（A 5 · B 6 · C 10） |
| 提交数 | 10（A 2 · B 3 · C 5） |
| 推荐顺序 | A1–A3 → B → C → A4–A5（A4–A5 描述 C 落地后的行为） |
| 阻塞 | A、B 无阻塞项；C 有 4 项需 owner 先定（§8） |
| 立即副作用 | 本文件写入后 `docs map` 会报 1 条未登记文档；这是 A1 的失败测试，A1 未执行前回归不绿 |

---

## 1. 只读核验证据（本轮实测）

以下六条在计划阶段复现，未改任何文件。它们决定任务卡里的失败测试怎么写。

| # | 结论 | 复现方式 | 实测结果 |
| --- | --- | --- | --- |
| E1 | 审批状态进入内容哈希，review 与 release 互锁 | 用 `quality_content_sha256` 对同一份维度、只改 Q5 的 `reason` 求值 | review 时 `97fcc247…`，release 时 `03c7eefc…`，`equal? False` |
| E2 | 证书与门禁接受非法 Q 状态 | 构造 Q1–Q5 全为 `"BANANA"` 的质量报告，分别调 `certificate.issue` 与 `quality_gates.evaluate` | 证书 `verdict=pass, reason=None`；门禁 `verification_status=pass` |
| E3 | `package-verify` 信任 manifest 自报 | 手写包：所有 `sha256=null`、无分镜证据、两份 approval 的 `lesson` 是别的课程、`stage=release` 放进 review 槽 | `verify_package(root) == []` |
| E4 | 内容清单复核器有四处缺口 | ① `archived.from` 旧源仍存在；② cache 目标是文件；③ cache 目录内 junction 指向根外；④ junction 计数 | ①② `exit 0 / content manifest ok`；③④ 计数 `3 != 1`（跟随 junction 数到根外文件） |
| E5 | `session-run` 无条件门禁打破 fixture 验收 | `scripts/check-session.ps1`、`check-python-session.ps1` 等对 `CourseControl/tests/fixtures/lesson-smoke` 跑 `session-run`；fixture 有 `storyboard.yaml` 但无签字 | 门禁必然 `blocked`，退出码 3 |
| E6 | mtime 回退在异常时用旧输入集 | `_mtime_freshness` 的 `except (AttributeError, OSError)` 分支写死一份旧输入列表 | 旧列表文件齐全且更旧时返回 `fresh`（fail-open） |

补充事实（影响任务边界）：

- 内容根由 `config/local-paths.yaml` 的 `content_root` 决定；当前清单复核器对真实清单返回 `content manifest ok`。
- `deliver/` 下已有 17 个包；本轮不改它们，但严格化后的 `package-verify` 会让旧包报出新问题（§8 决策 6）。
- 现有签字与审批记录里 `approved_by` 全是字面量 `"human"`（`authoring/models.py:199`、`authoring/pipeline.py:461,575`），`author-accept` 与 `storyboard-review` 都没有 `--by`。这是"机器自动生成 human"的直接证据。
- 内容异常队列中的 `owner` 是占位符 `"owner"`（`<内容根>/build/_shared/frame-audit/episode/content-exceptions.json`）。

---

## 2. 核心设计（三个子项目共用的约束）

### 2.1 内容与审批分离

```
quality-report.json
├── dimensions: [Q1..Q5]           ← 只放可复算的内容事实
│     Q5.artifacts: 产物是否齐全   ← 内容事实（参与哈希、参与阻断）
├── approvals: {review, release}   ← 审批状态（不参与内容哈希）
└── content_sha256                 ← 对「Q1–Q4 + Q5 产物事实 + 相关 risks + 分镜签字哈希」求值
```

规则：

1. **内容投影**只含可复算事实：Q1–Q4 的状态与理由、Q5 的产物存在性、分镜签字文件的 sha256、由这些事实派生的 risks。
2. **审批状态**（review/release 是否具名批准、批准时间）单独存放，**不进 content hash**，也不进 `BLOCKED_WARNINGS`。
3. 因此 `review 批准 → release 批准` 这条路径上 content hash 恒定；`release-approve` 写完审批后复算一次，哈希不一致即拒绝（这是防篡改断言，不是死锁）。
4. `states.RELEASE_APPROVED` 这类派生布尔值**读取时复算**，不作为证据被信任。

### 2.2 一套证据函数

新增 `course_control/quality/evidence.py`，四个入口共用：

| 函数 | 职责 |
| --- | --- |
| `normalize_dimensions(report)` | 封闭枚举 `{PASS, WARN, BLOCKED, INCOMPLETE, FAIL}`；缺失、重复、未知一律归一为 `INCOMPLETE`，并返回原因 |
| `quality_content(report)` | 生成 2.1 的内容投影（无审批字段） |
| `quality_content_sha256(report)` | 对投影求值；`certificate.py` 的旧函数改为转发，保持兼容 |
| `approval_problems(review_path, release_path, *, lesson, build_report, final_video, quality)` | 校验：存在、`decision=approved`、`approved_by` 具名且不在机器名黑名单、`lesson` 相同、`stage` 与槽位一致、三个哈希绑定当前证据 |
| `evidence_problems(...)` | `release-check` 的步骤、`release-approve` 的前置条件、`package` 的 verdict、`package-verify` 全部调用它；不允许各自复制判断 |

### 2.3 具名审批

- 审批写入必须带 `--by <name>`；`approve()`、`sign_storyboard_page()`、`storyboard-review` 都接收审批人。
- 机器名黑名单（大小写不敏感）：`human`、`owner`、`system`、`claude`、`claude code`、`ai`、`assistant`、`automation`、`bot`、`n/a`、`none`、`unknown`。
- 已存在的 `"human"` 记录不迁移（内容归用户），但新流程与 `package-verify` 会拒绝；见 §8 决策 1。

### 2.4 发布顺序

```
S8 release-check（自动，全链）
→ S9 release-approve（人工，具名；先跑同一套全链）
→ package（只有证据齐备才 pass；非 pass 不覆盖旧交付）
→ package-verify（重算证据）
```

现文档的 S9 顺序（package → package-verify → release-approve）必须改：package 在 release 批准之前永远只能是 `incomplete`。

### 2.5 全局 fail-closed 规则

以下任一情况必须 `INCOMPLETE`/非零退出，不得继续：`ContractError`、文件缺失、非法状态、未知 `schema_version`、重复条目、无法解析的队列、路径越界、junction 越界。

---

## 3. 子项目

### 3.1 A · 文档治理

**职责**：文档地图唯一、命令链机读可校验、验收矩阵可校验、记录层如实。

**文件清单**

| 文件 | 改动 |
| --- | --- |
| `docs/superpowers/plans/2026-11-16-tooling-convergence.md` | 本文件 |
| `docs/文档地图.yaml` | 登记本文件（`layer: record`、`status: record`）；补 `questions` 与各文档的 `answers` |
| `docs/README.md` | 由 `check_docs.py --write` 生成，不手改 |
| `docs/阅读顺序.md` | 补"已取代"状态横幅（当前唯一缺横幅的 `superseded` 文档） |
| `docs/生产流水线-阶段与中间交付物.md` | 增加机读阶段表（fenced yaml）；S9 顺序改为 approve → package → verify；写明共同证据函数与具名审批 |
| `docs/ACCEPTANCE.md` | 增加机读验收矩阵（命令 → 期望退出码/状态词）；补 `release-approve`、`package`、`package-verify` 的新语义 |
| `docs/DECISIONS.md` | 追加两条决策：内容哈希不含审批状态；package 在 release 批准之后 |
| `docs/audit/handoff-2026-11-16.md` | 记录本轮修复与最终 SHA（记录层） |
| `scripts/check_docs.py` | 增加结构校验、阶段表校验、验收矩阵校验与对应 selftest 负例 |

**边界**：A 只改文档与 `check_docs.py`；不碰 `CourseControl/`、`scripts/` 其他脚本、内容根。

**依赖**：A1–A3 可立即做；A4–A5 依赖 C6/C7 落地后的真实行为。

### 3.2 B · 内容根与 build 布局

**职责**：内容清单可被独立复核；junction 不被跟随；归档与缓存有类型与计数约束；异常队列绑定课程、责任人、原因与解除条件。

**文件清单**

| 文件 | 改动 |
| --- | --- |
| `scripts/verify_content_manifest.py` | junction 安全遍历；`archived.from` 必须消失；cache 目标必须是目录并核对文件数与字节数；非 cache 核对 files/bytes/tree_sha256；未知版本与缺字段 fail-closed；新增 `--selftest` |
| `scripts/check_build_layout.py` | build 顶层与课内 junction 必须报错；大小统计不跟随 junction；selftest 增加 junction 负例 |
| `scripts/check.ps1` | 接入 `verify_content_manifest.py --selftest` 与真实清单复核（内容根存在时） |
| `CourseControl/src/course_control/quality/exceptions.py` | **新增**：带 `StrictModel` 的内容异常 schema 与读取器 |
| `CourseControl/src/course_control/release/check.py` | 仅改 `content_exception_for`：委托新模块，返回结构化原因 |
| `CourseControl/tests/test_content_exceptions.py` | **新增** |
| `docs/audit/content-changes-2026-11-16.json` | 补齐 cache 的 `bytes`、archive 的 `kind`；不改历史 from/to |
| `docs/audit/content-changes-2026-11-16.md` | 表格同步加"旧源已消失/目标类型"两列 |

**边界**：B 拥有 `content_exception_for` 与异常 schema；C 只调用，不再改这个函数。`release/check.py` 的其余部分归 C。

**依赖**：B1 → B2 → B3 → B4 → B5 → B6。B5 先于 C5 落地（同一文件）。

### 3.3 C · 课程就绪与发布证据

**职责**：Q 状态封闭且完整；证书与门禁不接受非法值；release-check / release-approve / package / package-verify 共用同一套证据；人工审批具名；失败不覆盖交付。

**文件清单**

| 文件 | 改动 |
| --- | --- |
| `CourseControl/src/course_control/quality/evidence.py` | **新增**：§2.2 的五个函数与封闭枚举 |
| `CourseControl/src/course_control/quality/quality.py` | 维度归一；Q5 拆成"产物事实"与"审批状态"；`BLOCKED_WARNINGS` 不含审批派生项；content hash 用投影 |
| `CourseControl/src/course_control/quality/certificate.py` | 改用封闭枚举；缺失/重复/未知 → `INCOMPLETE`；`quality_content_sha256` 转发 |
| `CourseControl/src/course_control/quality/quality_gates.py` | 未知 Q 状态计入 incomplete；Q5 审批派生 WARN 不阻断 |
| `CourseControl/src/course_control/release/check.py` | `_lesson_steps` 用共同证据；证书按内容投影签发；`release-check` 保持全链 |
| `CourseControl/src/course_control/release/build_manifest.py` | mtime 回退遇异常直接 stale，删除旧输入列表 |
| `CourseControl/src/course_control/delivery/package.py` | verdict 与 `verify_package` 改用共同证据；重算而非信任 manifest |
| `CourseControl/src/course_control/cli/producer.py` | `release-approve` 先跑 `run_release_check`；审批写 `lesson`/`stage`；写后复算 content hash 必须不变；`package-verify` 去重 |
| `CourseControl/src/course_control/cli/session.py` | 身份校验始终执行；分镜签字只对内容根课程强制 |
| `CourseControl/src/course_control/cli/scene.py` | 同上口径（同一判定函数） |
| `CourseControl/src/course_control/cli/authoring.py` | `author-accept --by`、`storyboard-review --by` |
| `CourseControl/src/course_control/authoring/pipeline.py` | `approve()`、`sign_storyboard_page()` 接收具名审批人；断言拒绝机器名 |
| `CourseControl/src/course_control/authoring/models.py` | `ApprovalEntry.approved_by` 去掉默认值 `"human"` |
| `CourseControl/tests/test_evidence.py` | **新增** |
| `CourseControl/tests/test_release_approve.py` | **新增**（端到端） |
| `CourseControl/tests/test_package.py` | 补负例：null 哈希、lesson/stage 错配、缺分镜、schema 未知、fail 不覆盖 |
| `CourseControl/tests/test_quality.py`、`test_certificate.py`、`test_quality_gates.py` | 非法/缺失/重复 Q 状态负例；审批前后哈希恒定 |
| `CourseControl/tests/test_session.py` | 两条门禁分支 |
| `CourseControl/tests/test_authoring_gate.py`、`test_storyboard_page.py` | 具名审批；缺 `--by` 拒绝 |
| `CourseControl/tests/test_release_stale.py` | mtime 回退异常 → stale |

**边界**：C 不改 `docs/`（文档由 A 同步），不改内容根与 `deliver/`。

**依赖**：C1 → C2 → C3 → C4 → C5 → C6 → C7 → C8 → C9 → C10。

---

## 4. 最新评审逐项追踪

| 编号 | 评审原文（摘要） | 处置 | 理由与证据 | 落点 |
| --- | --- | --- | --- | --- |
| P1-1 | 审批状态参与 content hash，review/release 死锁；`release-approve` 没走完整链 | **fix** | E1 实测哈希不相等。根因：`quality_content_sha256` 含 Q5 状态与 reason，Q5 reason 随审批变化；`release-approve` 只读 `build_quality_report`、`gate.json`、review 文件，不跑 media QC / 字幕 QC / defects / 证书。另：`states.RELEASE_APPROVED` 在批准前写入为 false，package 读取时永远为 false，重跑报告又会改哈希 | C1、C2、C3、C4、C6 |
| P1-2 | `package-verify` 仍信任 manifest 自报 | **fix** | E3 实测 `verify_package == []`：所有 `sha256` 为 null 仍通过（`if item.get("sha256")`），审批不校验 `lesson`/`stage`，分镜证据是否必需由 manifest 的 `evidence.storyboard` 决定 | C7 |
| P1-3 | certificate 与 gate 接受非法 Q；Q1–Q5 不完整不强制 INCOMPLETE | **fix** | E2 实测 `BANANA` 两处都 pass。`_BAD` 只做成员判断；门禁只识别少数状态。缺维度目前只由证书的 `missing` 覆盖，门禁没有 | C1、C3、C4 |
| P1-4 | 清单复核器不验 `archived.from`、cache 目标类型与文件数，跟随 junction | **fix** | E4 实测：旧源仍存在 → exit 0；cache 目标是文件 → exit 0；cache 内 junction 使计数 `3 != 1`。`_within` 的 `resolve()` 与缓存目录的 `rglob("*")` 都会跟随 junction | B1、B2 |
| P2-1 | `session-run` 无条件门禁破坏 lesson-smoke fixture 回归 | **fix** | E5。签字门保护的是动效/配音/渲染，不是代码会话执行；但会话证据也不能绕过身份校验。改为：身份始终校验；分镜签字只对 `<内容根>/lessons/` 下的课程强制。fixture 在仓库 `CourseControl/tests/fixtures/`，只走身份校验 | C9 |
| P2-2 | mtime 回退发现异常仍用旧输入集 | **fix** | E6。`except` 分支写死 `timeline.spec.json` 等旧路径，可能更旧 → 返回 fresh。改为异常即 stale 并写明原因 | C10 |
| P2-3 | cache 计数跟随 junction | **fix** | E4③④。`Path.rglob` 会进入 junction。改为统一 `os.walk(followlinks=False)` + junction 检测 | B1、B2 |
| P2-4 | 缺 `release-approve` 端到端与 package 负例 | **fix** | `CourseControl/tests/` 无 `test_release_approve.py`；`test_package.py` 只有正向与路径穿越，没有 null 哈希、审批错配、缺分镜、未知 schema | C6、C7 |

无 defer、无 not applicable。

---

## 5. 任务卡

每张卡固定四段：**失败测试**（先写、必须先红）→ **最小实现** → **验证命令** → **预期输出**。

### A · 文档治理

#### A1 · 计划文档入图，`docs map` 恢复绿

- **失败测试**：本文件已写入后运行 `check_docs.py`，报 `document is not in the map: superpowers/plans/2026-11-16-tooling-convergence.md`。
- **最小实现**：在 `docs/文档地图.yaml` 的 `documents` 增加 `{path: superpowers/plans/2026-11-16-tooling-convergence.md, layer: record, status: record, answers: 本轮工具链收敛的任务、顺序与验收}`；运行 `--write` 重生成 `docs/README.md`。
- **验证命令**：`uv run --project CourseControl python scripts/check_docs.py --workspace .`
- **预期输出**：`docs map ok (105 documents)`，退出码 0；`--selftest` 仍打印 `docs map selftest PASS`。

#### A2 · 文档地图结构校验

- **失败测试**：selftest 新增三例——`questions` 指向未登记文档、`layer` 拼错、`superseded` 文件无状态横幅。当前实现不检查 `questions`，只检查 `layer` 枚举，从不检查横幅 → 三例全过（红）。
- **最小实现**：`structure_errors()`：`questions[*].path` 必须是已登记的 `current` 文档；`data["layers"]` 必须与 `LAYER_ORDER` 等长同序；`status=superseded` 的文件前 600 字符必须含"已取代/SUPERSEDED/superseded"；`superseded_by` 目标必须已登记。给 `docs/阅读顺序.md` 补横幅。
- **验证命令**：`uv run --project CourseControl python scripts/check_docs.py --workspace . ; uv run --project CourseControl python scripts/check_docs.py --selftest`
- **预期输出**：`docs map ok (105 documents)`；`docs map selftest PASS`。

#### A3 · 阶段表机读化并对命令注册表校验

- **失败测试**：selftest 新增 `pipeline_stage_missing`：从阶段 YAML 删掉 S7 → 期望报错。当前没有解析器 → 无报错（红）。另加 `pipeline_unknown_command`：把 S4 的 `storyboard-page` 改成 `storyboard-pages` → 期望报错。
- **最小实现**：在 `docs/生产流水线-阶段与中间交付物.md` 增加 fenced yaml 块：

  ```yaml
  pipeline:
    stages:
      - id: S0
        commands: [project-validate, validate, preflight]
        artifacts: [...]
        gate: auto+human
  ```

  `check_docs.py --check-pipeline`（默认开启）解析该块，断言：S0–S9 恰好各一次；每个 `commands` 成员在 Typer 注册表中存在；G0–G7 对照表覆盖每个 stage；每个 stage 至少一个 command 与一个 artifact。
- **验证命令**：`uv run --project CourseControl python scripts/check_docs.py --workspace .`
- **预期输出**：`pipeline ok (10 stages)`，随后 `docs map ok (105 documents)`；selftest PASS。

#### A4 · 验收矩阵机读化（依赖 C6/C7）

- **失败测试**：selftest 新增 `acceptance_unknown_command` 与 `acceptance_missing_gate`：验收块列一个不存在的命令、或漏掉 `release-approve` → 期望报错。当前无解析器（红）。
- **最小实现**：`docs/ACCEPTANCE.md` 增加 fenced yaml `acceptance:` 块（`command`、`fixture`、`expected_exit`、`expected_status`）；`check_docs.py --check-acceptance` 断言命令存在、关键命令集合 `{release-check, release-approve, package, package-verify, quality-report, quality-gate}` 全覆盖、每行有非空期望。
- **验证命令**：`uv run --project CourseControl python scripts/check_docs.py --workspace . ; uv run --project CourseControl python scripts/check_docs.py --selftest`
- **预期输出**：`acceptance matrix ok (N rows)`；selftest PASS。

#### A5 · 契约与记录同步（依赖 C6/C7）

- **失败测试**：`check_docs.py` 的链接检查在新增引用指向尚不存在的文件时报 `broken link`；先写链接、后补文件即可见红。
- **最小实现**：更新 `生产流水线` S9 顺序、`ACCEPTANCE` 状态词、`DECISIONS` 两条决策、`docs/audit/handoff-2026-11-16.md` 本轮记录与最终 SHA。
- **验证命令**：`uv run --project CourseControl python scripts/check_docs.py --workspace .`
- **预期输出**：无 `broken link`、无 `unknown subcommand`；`docs map ok (105 documents)`。

### B · 内容根与 build 布局

#### B1 · junction 安全遍历

- **失败测试**：`verify_content_manifest.py --selftest` 用例 `cache_junction`：临时内容根下 `cached/` 含 1 个文件，`cached/link` 是指向根外含 2 个文件的 junction，清单声明 `files: 1`。当前 `rglob` 跟随 → 报 `3 != 1`（实测）。
- **最小实现**：新增 `walk_tree(root)`：`os.walk(followlinks=False)`，目录项用 `is_symlink()` 与 `Path.is_junction()` 识别 junction，命中即记录并 `dirnames.remove`；返回 `files/bytes/symlinks/junctions/tree_sha256`。`tree()` 与 cache 计数共用。
- **验证命令**：`uv run --project CourseControl python scripts/verify_content_manifest.py --selftest`
- **预期输出**：`verify content manifest selftest PASS`；真实清单复核 `content manifest ok`，退出码 0。

#### B2 · 归档旧源、目标类型与计数

- **失败测试**：selftest 三例——`archived_from_exists`（`from` 文件仍在 → 期望报错，当前 exit 0）、`cache_target_is_file`（cache 目标是文件 → 期望报错，当前 exit 0）、`cache_nested_junction`（B1 用例，期望报错）。
- **最小实现**：`archived` 增加 `from` 必须不存在、`to` 必须是文件、`bytes` 与 `sha256` 必须匹配；`moves` 的 `cache` 分支要求 `to` 是目录、`files`/`bytes` 与 `walk_tree` 一致；非 cache 分支增加 `bytes` 比较。任一声明字段缺失视为格式错误。
- **验证命令**：`uv run --project CourseControl python scripts/verify_content_manifest.py --selftest ; uv run --project CourseControl python scripts/verify_content_manifest.py --manifest docs/audit/content-changes-2026-11-16.json --content-root <内容根>`
- **预期输出**：selftest PASS；`content manifest ok`。

#### B3 · 清单格式 fail-closed

- **失败测试**：selftest 四例——`schema_version` 缺失或非 1、`moves` 不是列表、条目缺 `to`、JSON 不可解析 → 期望各自 exit 1 并指名条目。当前全部 exit 0 或抛未处理异常。
- **最小实现**：入口先校验 `schema_version == 1` 与各顶层键的类型；捕获 `OSError/JSONDecodeError` 返回 1；所有错误走同一 `problems` 列表。
- **验证命令**：`uv run --project CourseControl python scripts/verify_content_manifest.py --selftest`
- **预期输出**：`verify content manifest selftest PASS`。

#### B4 · build 布局拒绝 junction

- **失败测试**：`check_build_layout.py --selftest` 新增 `junction_at_top`：`build/<slug>` 是 junction → 期望报错；`junction_in_lesson`：`build/<slug>/final` 是 junction → 期望报 advisory 且不计入大小。当前 `is_dir()` 跟随 junction，大小 `rglob` 也跟随。
- **最小实现**：`audit()` 用与 B1 相同的 junction 检测；顶层 junction 记为 error（`is a junction, not a directory`）；课内 junction 记入 advice 并从大小统计排除。
- **验证命令**：`uv run --project CourseControl python scripts/check_build_layout.py --selftest`
- **预期输出**：`build layout selftest PASS`。

#### B5 · 内容异常队列 schema

- **失败测试**：`test_content_exceptions.py` 三例——① 条目缺 `clear_when` → 期望 `INCOMPLETE` 且原因点名缺字段；② `status: cleared` 但没有 `cleared_by`/`cleared_at`/`rechecked_at` → 期望仍阻断；③ `lesson: "*"` 或缺失 → 不得匹配任何课程。当前 ① 被当作可用异常返回、② 直接视为已清除（fail-open）、③ 不匹配（现状安全但无 schema）。
- **最小实现**：新增 `quality/exceptions.py`：`ContentException(StrictModel)` 字段 `lesson, owner, scope, reason, clear_when, status, release_policy, captured`；`load_queue(build_root)` 校验顶层 `schema_version`、条目逐条校验，非法条目转成 `INCOMPLETE` 原因（不是"无异常"）；`for_lesson(lesson)` 只匹配精确 slug；`cleared` 必须带 `cleared_by`、`cleared_at`、`rechecked_at`。`release/check.py:content_exception_for` 委托它。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_content_exceptions.py"`
- **预期输出**：`Ran 8 tests ... OK`（数量以实现为准），0 失败。

#### B6 · 清单字段补齐与回归接入

- **失败测试**：B2 落地后对现有清单运行复核 → `cache ... missing bytes`、`archived ... missing kind`，退出码 1。
- **最小实现**：用 `walk_tree` 只读统计 `<内容根>` 现有目标，补齐 `moves[*].bytes`、`archived[*].kind`；`scripts/check.ps1` 增加两项 `Invoke-Checked`：`verify content manifest --selftest`、真实清单复核（内容根存在时）。
- **验证命令**：`uv run --project CourseControl python scripts/verify_content_manifest.py --manifest docs/audit/content-changes-2026-11-16.json --content-root <内容根>`
- **预期输出**：`content manifest ok`；`check.ps1` 中两项均不打印 `FAILED`。

### C · 课程就绪与发布证据

#### C1 · `quality/evidence.py` 与封闭枚举

- **失败测试**：新建 `test_evidence.py`：`Q3` 状态 `"banana"` → `normalize_dimensions` 返回 `INCOMPLETE`；Q6 出现 → `INCOMPLETE`；Q4 重复 → `INCOMPLETE`；`approved_by: "human"`、`lesson: other`、review 槽放 `stage: release` → `approval_problems` 非空。模块不存在时 import 失败（红）。
- **最小实现**：按 §2.2 实现五个函数；`Q_STATES = {"PASS","WARN","BLOCKED","INCOMPLETE","FAIL"}`；机器名黑名单集中在本模块。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_evidence.py"`
- **预期输出**：`Ran N tests ... OK`。

#### C2 · 质量报告：内容与审批分离

- **失败测试**：`test_quality.py` 新增 `test_content_sha256_is_stable_across_approvals`：同一 build 先求哈希，写 review+release 审批后再求哈希，必须相等。当前不相等（E1）。
- **最小实现**：`build_quality_report` 生成 `content_sha256` 时用 `quality_content()`；`dimensions` 中 Q5 只保留产物事实；审批状态移到 `approvals`（`review_approved`、`release_approved`、时间、审批人）并从 risks/blocking 中排除；`states` 里的审批布尔值改为读取时复算。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_quality.py"`
- **预期输出**：`Ran N tests ... OK`；新增用例断言两次哈希相等。

#### C3 · 证书：封闭枚举与完整性

- **失败测试**：`test_certificate.py` 三例——全 `"BANANA"` → `verdict != pass`（当前 pass，E2）；缺 Q3 → `INCOMPLETE`；Q4 重复 → `INCOMPLETE`。
- **最小实现**：`issue()` 调 `normalize_dimensions` 与 `quality_content_sha256`；任何归一后的 `INCOMPLETE` 进入 `reason`；`QUALITY_IDS` 完整性、重复、非法一律 `INCOMPLETE`。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_certificate.py"`
- **预期输出**：`Ran N tests ... OK`。

#### C4 · 门禁：非法 Q 与非阻断审批

- **失败测试**：`test_quality_gates.py` 两例——全 `"BANANA"` → `verification_status != "pass"`（当前 pass，E2）；review 已批、release 未批 → Q5 审批派生 WARN 不得进入 `blocking_warnings`，门禁在其余检查通过时为 `pass`。
- **最小实现**：`evaluate()` 用 `normalize_dimensions`；未知状态加入 `incomplete`；Q5 审批派生项不产生 warning。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_quality_gates.py"`
- **预期输出**：`Ran N tests ... OK`。

#### C5 · `release-check` 使用共同证据

- **失败测试**：`test_release_approve.py` 的 `test_release_check_reports_incomplete_before_approval`：证据齐全但未批准 → `status == "incomplete"`，步骤表含 `certificate` 且不是 PASS；`test_release_check_detects_wrong_lesson_approval`：审批属于别的课程 → 非 PASS。
- **最小实现**：`_lesson_steps` 的证书签发使用内容投影；`release-check` 的 `storyboard_signoff` 与异常步骤调共同证据函数；`content_exception` 调 B5 的读取器。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_release_approve.py"`
- **预期输出**：`Ran N tests ... OK`。

#### C6 · `release-approve` 走全链并打破死锁

- **失败测试**：`test_release_approve.py::test_review_then_release_then_package`：构造证据齐全的 lesson；`release-approve --stage review --by alice` → exit 0；`release-approve --stage release --by bob` → exit 0（当前因哈希变化 exit 2）；随后 `package` → verdict pass。另 `test_release_approve_runs_full_chain`：故意让 media-qc 缺失 → exit 2，且不写审批文件。
- **最小实现**：`release_approve_command` 先调 `run_release_check`，拒绝非 `pass`/`pass_with_exemption`；审批 payload 增加 `lesson`、`stage`、`quality_report_content_sha256`；写文件后重算报告，content hash 必须不变，否则删除刚写的文件并 exit 2；删除重复的 gate/review 判断。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_release_approve.py"`
- **预期输出**：`Ran N tests ... OK`；无 `automatic verification is not pass` 误报。

#### C7 · package / package-verify 重算证据

- **失败测试**：`test_package.py` 五例——① 所有 `sha256: null` → 非空问题；② approval `lesson` 是别的课程 → 非空；③ review 槽放 `stage: release` → 非空；④ 无分镜证据 → 非空；⑤ `schema_version: 2` → 非空。当前 ①–④ 全过（E3）。另加 `fail` verdict 不覆盖已安装包。
- **最小实现**：`_delivery_verdict` 与 `verify_package` 调 `evidence_problems`；`present` 条目必须带 64 位 sha256 且匹配；审批必须同 lesson、同 stage 槽、具名、非机器名；分镜证据对 lesson 包无条件必需，`review.json` 必须绑定 `page_sha256` 与 `decisions_sha256`；manifest `schema_version` 只接受 1（若 owner 同意升 2，则只接受 2，见 §8 决策 6）；`package-verify` CLI 不重复追加 verdict 问题。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_package.py"`
- **预期输出**：`Ran N tests ... OK`；负例均断言具体问题文本。

#### C8 · 具名审批

- **失败测试**：`test_authoring_gate.py` 与 `test_storyboard_page.py`——`author-accept` 无 `--by` → exit 2；`--by human` → exit 2；`--by alice` → 写入 `approved_by: "alice"`；`storyboard-review --by` 缺省 → exit 2。当前 CLI 无该选项（红）。
- **最小实现**：`models.ApprovalEntry.approved_by` 去默认值；`approve(..., approved_by)`、`sign_storyboard_page(..., approved_by)`；CLI 增加必填 `--by`；`evidence.is_named_approver()` 统一校验；所有调用点补参数，测试用 `test-reviewer`。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_authoring_gate.py" ; ... -p "test_storyboard_page.py"`
- **预期输出**：两组均 `OK`。

#### C9 · `session-run` / `scene-run` 门禁范围

- **失败测试**：`test_session.py` 两例——fixture 目录（仓库内）跑 `session-run` → 不受分镜签字阻断（退出码不为 3）；`<内容根>/lessons/<slug>` 下未签字 → 退出码 3。当前两例都 3（红）。
- **最小实现**：抽出 `storyboard_gate_required(workspace, lesson_dir)`：`lesson_dir.resolve()` 位于 `content_root(workspace)/lessons/` 之下才要求签字；身份校验（`lesson.yaml` 存在、`spec.lesson == lesson_dir.name`）无条件执行。`scene.py` 用同一函数。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_session.py"`
- **预期输出**：`Ran N tests ... OK`；`scripts/check-session.ps1`（Docker 可用时）不再因未签字失败。

#### C10 · mtime 回退 fail-closed

- **失败测试**：`test_release_stale.py::test_mtime_fallback_is_stale_when_inputs_cannot_be_enumerated`：建旧输入集文件并让它们比成片旧，monkeypatch `declared_inputs` 抛 `AttributeError` → 期望 stale。当前返回 fresh（E6）。
- **最小实现**：删除旧输入列表；`except` 分支返回 `Freshness(False, MTIME_WEAK, reason="stale: cannot evaluate declared inputs: ...")`；简化 tuple 判断。
- **验证命令**：`uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl -p "test_release_stale.py"`
- **预期输出**：`Ran N tests ... OK`。

---

## 6. 提交建议

每个提交独立可回滚，提交前跑对应验证命令。禁止把两个子项目混在一个提交里。

| 提交 | 子项目 | 内容 | 提交信息 |
| --- | --- | --- | --- |
| 1 | A | A1 + A2（入图、结构校验、阅读顺序横幅） | `docs: register the convergence plan and make the map checks structural` |
| 2 | A | A3（阶段表机读化 + 命令校验 + selftest） | `docs: check the stage table against the command registry` |
| 3 | B | B1–B3（junction 遍历、归档/缓存校验、格式 fail-closed、selftest） | `fix: verify the content manifest without following junctions` |
| 4 | B | B4（build 布局 junction 负例） | `fix: reject junctions in the build layout` |
| 5 | B | B5–B6（异常队列 schema、清单字段、check.ps1 接入） | `fix: bind content exceptions to a lesson, owner and clearing condition` |
| 6 | C | C1–C4（evidence 模块、Q 枚举、报告分离、证书与门禁） | `fix: one closed Q vocabulary for the report, certificate and gate` |
| 7 | C | C5–C6（release-check 共同证据、release-approve 全链、死锁测试） | `fix: make release-approve run the same evidence chain as release-check` |
| 8 | C | C7（package 与 package-verify 重算证据） | `fix: recompute package evidence instead of trusting the manifest` |
| 9 | C | C8（具名审批） | `fix: require a named human for every approval and sign-off` |
| 10 | C | C9–C10（会话门禁范围、mtime 回退） | `fix: scope the storyboard gate and fail closed on mtime fallback` |
| 11（可选） | A | A4–A5（验收矩阵、契约与记录同步） | `docs: record the evidence chain and the acceptance matrix` |

合计 **10 个必做提交**，1 个可选。A4–A5 必须在 C6/C7 之后。

---

## 7. 最终验收矩阵

| # | 验收项 | 子项目 | 命令 | 预期输出 |
| --- | --- | --- | --- | --- |
| 1 | 文档地图唯一且本文件已登记 | A | `uv run --project CourseControl python scripts/check_docs.py --workspace .` | `docs map ok (105 documents)`，exit 0 |
| 2 | 文档检查能红 | A | `... scripts/check_docs.py --selftest` | `docs map selftest PASS` |
| 3 | 阶段表与命令注册表一致 | A | 同上（默认解析） | `pipeline ok (10 stages)` |
| 4 | 验收矩阵完整 | A | 同上 | `acceptance matrix ok (N rows)` |
| 5 | 清单复核器能红 | B | `... scripts/verify_content_manifest.py --selftest` | `verify content manifest selftest PASS` |
| 6 | 真实清单复核通过 | B | `... scripts/verify_content_manifest.py --manifest docs/audit/content-changes-2026-11-16.json --content-root <内容根>` | `content manifest ok`，exit 0 |
| 7 | junction 不被跟随 | B | selftest 内 `cache_junction` 用例 | 声明 `files: 1` 时通过；声明 3 时失败 |
| 8 | 异常队列绑定四要素 | B | `python -m unittest ... -p "test_content_exceptions.py"` | `OK` |
| 9 | Q 状态封闭、缺失/非法即 INCOMPLETE | C | `-p "test_evidence.py"`、`-p "test_certificate.py"`、`-p "test_quality_gates.py"` | 三组 `OK` |
| 10 | 审批前后 content hash 不变 | C | `-p "test_quality.py"` | `OK`，含 `test_content_sha256_is_stable_across_approvals` |
| 11 | review → release → package 全链可达 | C | `-p "test_release_approve.py"`、`-p "test_package.py"` | 两组 `OK` |
| 12 | `package-verify` 重算证据 | C | `-p "test_package.py"` 五条负例 | 每条断言具体问题文本 |
| 13 | 具名审批生效 | C | `-p "test_authoring_gate.py"`、`-p "test_storyboard_page.py"` | 两组 `OK` |
| 14 | fixture 会话不被签字门挡住 | C | `-p "test_session.py"`；Docker 可用时 `scripts/check-session.ps1` | `OK`；脚本 exit 0 |
| 15 | mtime 回退 fail-closed | C | `-p "test_release_stale.py"` | `OK` |
| 16 | 全量回归 | 全部 | `.\scripts\check.ps1` | 末尾 `check ok`，exit 0；CourseControl 测试数 ≥ 806 且无 `test count dropped` |
| 17 | 没有碰内容与交付 | 全部 | `git status --porcelain`；`git diff --stat -- lessons deliver` | 只出现计划内文件；内容与交付零改动 |
| 18 | 非 pass 不覆盖交付 | C | `test_incomplete_attempt_does_not_replace_delivery`、新增 `fail` 用例 | `OK` |

fail-closed 负例清单（每项必须有测试）：非法 Q 状态、缺 Q 维度、重复 Q、未知 manifest schema、审批缺名/机器名/课程不符/槽位不符、证书未绑定当前内容、分镜证据缺失、路径穿越、junction 越界、清单旧源仍存在、cache 目标非目录、`ContractError` 未捕获。

---

## 8. 仍需人工决定

| # | 事项 | 现状 | 建议 | 影响 |
| --- | --- | --- | --- | --- |
| 1 | 旧审批记录里的 `"human"` 怎么处理 | 所有 `approval.json`、`storyboard-review.json` 都是 `"human"` | 不迁移内容；新签字必须具名；旧交付保留为历史记录，但 `package-verify` 会拒绝其审批。已有课程再次发布前需 owner 重新签一次 | C8、旧课重发 |
| 2 | S9 顺序 | 文档写 package → package-verify → release-approve | 改为 release-approve → package → package-verify | A5、C6 |
| 3 | `release-approve` 是否允许重写 build 证据 | 现在会重写 `quality-report.json` | 允许写入 `build/<slug>/quality/`，但审批文件写入后 content hash 必须不变；不接受则改为"先跑 release-check、批准时只读校验" | C6 |
| 4 | `session-run` 门禁范围 | 无条件 | 只对 `<内容根>/lessons/` 下的课程强制分镜签字；fixture 只校验身份 | C9 |
| 5 | 异常队列位置与 owner | 单一共享文件；`owner` 是占位符 `"owner"` | 每课 `build/<slug>/quality/content-exceptions.json`，共享文件降为导入；`owner` 必须是真人姓名，否则该条目按 INCOMPLETE 处理 | B5、t1-01 当前会被挡 |
| 6 | package manifest 版本 | `schema_version: 1`，旧包 17 个 | 保持 1 并严格化（旧包可能报问题），或升 2 并明确拒绝 1。建议升 2，旧包作为历史记录不再验证 | C7 |
| 7 | `docs/superpowers/` 的登记策略 | 未登记；check_docs 会报 | 每个计划文件在 `文档地图.yaml` 登记为 `record`（推荐）；或给 `superpowers/` 加排除规则 | A1 |
| 8 | Q5 是否保留为质量维度 | 当前 Q5 同时表达产物与审批 | 保留 Q5 名称，只放产物事实；审批移到 `approvals` | C2、C4 |

---

## 9. 执行前检查与已知副作用

1. **本文件未登记**：写入后 `check_docs.py` 会报 1 条未登记文档，`check.ps1` 因此不绿。A1 是它的失败测试；执行 A 的第一步就是修掉。
2. **基线复核**：每个子项目开工前先跑 `.\scripts\check.ps1`，确认从 `check ok` 出发；若变红，先停并报告，不带红基线开工。
3. **内容根**：B6 只读 `<内容根>`；不改课程、证据与 `deliver/`。清单字段补齐只改 `docs/audit/` 下的两个文件。
4. **夹具与 Docker**：`session-run` 的端到端验收依赖 Docker；不可用时单元测试覆盖门禁判定，脚本级验收记为 `not_run`，不得写成通过。
5. **提交边界**：不 push、不 reset、不重写历史；每个子项目完成后等 owner 指定下一个子项目。

---

## 10. 执行状态

**2026-11-16 owner 决定**：执行 A；A1–A3 必做；A5 改为必做但排在 C6/C7 之后；A4 本轮未要求，不做。A 完成后停止，不进入 B。

| 任务 | 状态 | 证据 |
| --- | --- | --- |
| A1 计划入图 | **完成** | `docs/文档地图.yaml` 增加 `record` 条目；`docs/README.md` 重新生成；`docs map ok (105 documents)` |
| A2 地图结构校验 | **完成** | `scripts/check_docs.py` 增加 `structure_errors`：`questions` 必须指向已登记的现行文档、`layers` 四个层必须有非空说明、`superseded` 文件前 600 字符必须有状态横幅、`superseded_by` 必须已登记；selftest 新增 4 个负例 |
| A3 阶段表机读化 | **完成** | 生产流水线文档新增 §2.3 `pipeline:` yaml 块（S0–S9、命令、产物、门）；`check_docs.py` 增加 `pipeline_data` / `pipeline_errors`；输出 `pipeline ok (10 stages)` |
| A5 契约与记录同步 | **待做（C6/C7 之后）** | 更新 S9 顺序、`ACCEPTANCE` 状态词、`DECISIONS` 两条决策、handoff 记录 |

**实现时的两处口径修正**（比计划更准确，已写在代码注释里）：

1. `layers` 校验改为"四个层都有非空说明、没有未知层"，不比较键的顺序——YAML 序列化会按键排序，比较顺序会产生假红。
2. G0–G7 的覆盖是"每个门至少被一个阶段引用"，不是"每个阶段至少一个门"——S1（研究）按设计没有 G 门，原写法会要求伪造一个。

**A 的验收输出**：

```
$ uv run --project CourseControl python scripts/check_docs.py --workspace .
pipeline ok (10 stages)
docs map ok (105 documents)

$ uv run --project CourseControl python scripts/check_docs.py --selftest
docs map selftest PASS
```

### B · 内容根与 build 布局（2026-11-16）

owner 口径：**每课异常队列、共享索引、具名 owner**。

| 任务 | 状态 | 证据 |
| --- | --- | --- |
| B1 junction 安全遍历 | **完成** | `walk_tree` 用 `os.walk(followlinks=False)` + symlink/junction 检测；`--selftest` 的 `cache junction` 用例证明计数不再进入根外（声明 1 个文件时通过） |
| B2 归档旧源、目标类型与计数 | **完成** | `archived.from` 必须消失、`to` 必须是普通文件、`kind=file`、字节与哈希匹配；move 支持目录与单文件；cache 要求真实目录、文件数与 junction 报告 |
| B3 清单格式 fail-closed | **完成** | `schema_version` 必须为 1；各 section 必须是列表；条目缺字段、路径越界、JSON 不可解析均报错退出 |
| B4 build 布局拒绝 junction | **完成** | 顶层 junction 记为 error；课内 junction 记入 advice 且不参与大小统计；`--selftest` 覆盖两类反例 |
| B5 异常队列 schema | **完成** | 新增 `quality/exceptions.py`：`ContentException` 强类型；`cleared` 必须带具名 `cleared_by`、`cleared_at`、`rechecked_at`；`lesson="*"`、占位 owner、缺 `clear_when` 一律阻断；`test_content_exceptions.py` 13 个用例 |
| B6 清单字段与回归接入 | **完成** | frame-audit 缓存改为 `files: 33` + `exclude: episode/content-exceptions.json`；`check.ps1` 接入 verifier selftest，并改为写每课队列与共享索引 |

**实现时的口径修正**（比计划更准确）：

1. **cache 只验类型、文件数与 junction，不验字节数。** 缓存每次回归都会重写，字节随内部时间戳变化；强验字节会让历史清单每次回归后都变红。非 cache 的 move 仍验 files/bytes/tree_sha256/symlinks。
2. **共享索引迁出缓存目录**：索引写在 `<内容根>/build/_shared/exceptions/index.json`；旧的 `frame-audit/episode/content-exceptions.json` 只作 legacy 导入，迁移后写成空 entries，并从 frame-audit 缓存的计数中排除。
3. **check.ps1 不发明人名**：新条目 `owner: "unassigned"`，由校验器判为“不是具名的人”并阻断；`t1-01` 在 owner 改成真人姓名前保持 INCOMPLETE。这正是“具名 owner”的执行方式。
4. **live manifest 不作为常驻闸门**：只把 verifier 的 selftest 接入 `check.ps1`；真实清单复核是审阅时的手工命令（缓存会被回归重写）。
5. **计划文件自身的绝对路径改成 `<内容根>`**：A 的计划在 A 回归时还未跟踪，B 回归开始扫描它，`path check` 因此首先变红；替换后 `path check ok`。

**B 的验收输出**：

```
check summary: checks=53 failed=0 content_exceptions=1
check ok
content exceptions: 1 (queued at <内容根>/build/t1-01-why-aerodynamics/quality/content-exceptions.json)

$ ... verify_content_manifest.py --selftest
verify content manifest selftest PASS
$ ... verify_content_manifest.py --manifest docs/audit/content-changes-2026-11-16.json --content-root <内容根>
content manifest ok
$ ... check_build_layout.py --selftest
build layout selftest PASS
$ ... -p "test_content_exceptions.py"
Ran 13 tests ... OK
```

### B 收口（2026-11-16，第三方复核 FAIL 后）

owner 批准的两条口径：`cleared` 只在新的失败观测晚于 `rechecked_at` 时重开；检查通过写 `resolved` 并保留 entry。

| 复核项 | 处置 | 证据 |
| --- | --- | --- |
| 队列与 `course-control checks` 冲突 | **修复** | 队列改为 `build/<slug>/quality/content-exceptions.json`；`checks` 的 `quality/exceptions.json` 不读不写；旧文件由写入器迁移后释放 |
| 写入器丢数据 / 误关闭 | **修复** | 写入器移到 Python：先校验再原子替换；损坏的 queue/index/legacy 一律拒绝且原文件字节不变；损坏或他课条目直接失败 |
| `cleared` 历史被覆盖 | **修复** | 重开时把旧的人工清除写入 `observations` 再改为 `incomplete`；早于 `rechecked_at` 的失败保留 `cleared` |
| 成功检查删除记录 | **修复** | 成功写 `status: resolved` + `resolved_at` + `resolved_by_check` + `resolved_run`，entry 与历史保留；不伪造 `cleared` |
| verifier 多个 fail-open | **修复** | 五个 section 必须齐全且为列表；`schema_version` 必须是整数 1；`cache` 必须严格布尔；`exclude` 只收安全的相对路径；逐级拒绝祖先 junction；junction 用例跑不了时 selftest 返回非零 |
| reader 对损坏输入不严 | **修复** | 缺/`null` `entries`、非 UTF-8、非法索引项、无时区/未来/倒序时间、非法 observation 一律阻断 |
| 写入器没有测试 | **修复** | `test_content_exceptions.py` 39 个用例：重开、旧失败不重开、损坏不覆盖、成功留痕、legacy 多条目、checks 互操作、他课条目拒绝 |
| 文档仍指旧路径 | **修复** | `ACCEPTANCE.md` 改为每课 `content-exceptions.json` + 共享索引；历史 handoff 保持原样（记录层） |

**实现口径**：

- `cleared` 只能由人写入；`exception-observe` 只接受 `open` / `resolved`，没有 `cleared` 参数。
- 时间必须是带时区的 ISO 8601；缺失、无时区、未来（允许 5 分钟时钟偏差）或倒序一律 fail-closed。
- 写入器保留人工填写的 `owner`/`scope`/`reason`/`clear_when`，回归只追加观测。
- 共享索引由队列派生：有阻塞条目则列出该课，全部 `cleared`/`resolved` 则移除。

**B 收口的最终回归**：

```
check log: <内容根>/runtime/logs/check-20261116-233638.log
check summary: checks=53 failed=0 content_exceptions=1
check ok

CourseControl: Ran 845 tests ... OK (skipped=9)
ModelingStudio 33 · ai_runtime 50 · ContentQA 25 · ManimSandbox 18 · KnowledgeStudio 40
```

仍未关闭：`t1-01` 的内容异常仍是 `incomplete`，原因是 `owner = "unassigned"` 不是具名的人；这需要 owner 本人把队列里的 `owner` 改成姓名，不是 B 的代码缺陷。旧共享队列文件保留为空 entries 的 legacy 记录（已排除出 frame-audit 缓存计数）。B 未提交。

### C · 课程就绪与发布证据（2026-11-16）

按 §8 的默认决策执行：旧 `"human"` 审批不再接受；S9 顺序改为 release-approve → package → package-verify；批准时允许写 build 证据但内容哈希必须不变；会话门禁只对内容根课程强制；package schema 升到 2；Q5 拆成产物事实与审批状态。

| 任务 | 状态 | 证据 |
| --- | --- | --- |
| C1 统一证据模块 | **完成** | 新增 `quality/evidence.py`：封闭 Q 枚举、内容投影、`approval_problems`、`evidence_problems`；9 个 `test_evidence` 用例 |
| C2 报告内容/审批分离 | **完成** | Q5 只放产物事实；审批进 `approvals`；`content_sha256` 在 review→release 前后恒定；`test_quality` 覆盖 |
| C3 证书封闭枚举 | **完成** | 缺/重复/非法 Q 一律 `INCOMPLETE`；证书 pin 内容哈希 |
| C4 门禁封闭枚举 | **完成** | 未知 Q 计入 incomplete；Q5 审批派生 WARN 不再阻断；3 个 `evaluate` 负例 |
| C5 release-check 共同证据 | **完成** | 返回 `approval_problems` 与 `delivery_allowed`；CLI 在未批准时退出 3 并打印原因 |
| C6 release-approve 全链 | **完成** | 先跑 `run_release_check`；审批写 `lesson`/`stage`/三方哈希；写后复算内容哈希，变化即删除并退出 2；5 个 `test_release_approve` 用例 |
| C7 package/verify 重算 | **完成** | schema 2；`present` 条目必须 64 位 sha256；审批按 lesson/stage/具名/哈希校验；分镜按 `storyboard_required`；证书 pin 内容；`test_package` 18 个用例 |
| C8 具名审批 | **完成** | `author-accept --by`、`storyboard-review --by`、`subtitles-accept --by`；`ApprovalEntry.approved_by` 无默认值；decisions 记录 `reviewed_by`；`assert_storyboard_signed` 拒绝机器名 |
| C9 会话门禁范围 | **完成** | `is_course_lesson`：只对 `<内容根>/lessons/` 下的课程要求分镜签字；fixture 只校验身份；`scene-run` 本就只解析内容根课程 |
| C10 mtime 回退 | **完成** | 输入集无法枚举即 stale，不再使用写死的旧列表 |
| C11 包隔离 | **完成** | 输出根、临时/备份/attempt 目录不得是链接；源文件与包内条目拒绝 symlink/junction 及祖先；`delivery_root_for` 不再 resolve；失败与 `fail` 都不覆盖已安装包 |
| A5 契约与记录同步 | **完成** | 生产流水线 S9 与机读表改为 approve→package→verify；ACCEPTANCE 更新交付顺序与包复核；DECISIONS 新增 D-105（内容/审批分离）与 D-106（交付顺序与 schema 2） |

**实现口径**：

- `release-check` 的 `status` 只表示自动检查；`delivery_allowed` 还要求两份具名审批成立。CLI 在 `status=pass` 但未批准时退出 3 并打印 `delivery: not allowed`。
- `release-approve` 的 review 阶段不要求 release 审批；release 阶段要求 review 审批已绑定当前内容。
- `package` 的 `pass` 需要证书 pass、Q1–Q5 封闭完整、两份审批、分镜签字与无开放内容异常；`incomplete` 与 `fail` 都写 `.attempt`。
- 旧 schema 1 包不再通过 `package-verify`，作为历史记录保留。

**C 的定向结果**：

```
CourseControl: Ran 877 tests ... OK (skipped=9)
docs map ok (105 documents)
pipeline ok (10 stages)
path check ok
```

**C 的最终回归**：

```
check log: <内容根>/runtime/logs/check-20261116-235607.log
check summary: checks=53 failed=0 content_exceptions=1
check ok

CourseControl: Ran 877 tests ... OK (skipped=9)
ModelingStudio 33 · ai_runtime 50 · ContentQA 25 · ManimSandbox 18 · KnowledgeStudio 40
```

第一次回归失败的原因是把 `_release_exit` 插在 `@app.command("release-check")` 与 `release_check` 之间，Typer 把 `dict` 参数当成命令参数，所有 CLI 命令注册失败；装饰器移回后第二次回归全绿。这个错误由 `course-control --help` 与五个受影响命令的冒烟检查在回归前本可发现，后续插入辅助函数时先跑一次 CLI 注册检查。

### C 收口与开发/生产边界（2026-11-17）

第三方复核的 10 条全部核实为真（P0 输出根、主题片审批、`assert_approved`、写入顺序、分镜门禁链接、`package-verify` 分镜自报、`quality_report_sha256` 过期、异常队列 legacy/时序/链接、exclude 前缀）。按 owner 决定：先冻结开发/生产边界，再修 P0/P1；旧包标记历史；质量相关 schema 升 2；删除 `quality_report_sha256`。

**路径边界（D-107）**

| 入口 | 行为 |
| --- | --- |
| `check.ps1` | 建 `%TEMP%/CourseWorkspace/run-<id>` 隔离根；`COURSEWORKSPACE_MODE=dev` + 开发根/开发 workspace；单元测试、夹具、frame audit、异常队列、日志全在该根；成功删除运行根，日志留在 `%TEMP%/CourseWorkspace/state/last-check.log` |
| Python dev 模式 | 仓库 workspace → 开发根；临时 workspace → 自身或显式临时根；解析到生产根的配置直接拒绝；不读生产 config/env |
| 生产命令 | `release-check`、`release-approve`、`package` 拒绝 dev 模式，要求显式生产内容根；`package` 只写 `<内容根>/deliver/<slug>`，无 `--out` |
| 证明 | 最终 dev 回归前后，生产内容根的目录/队列/日志/audit 缓存时间戳与大小完全一致 |

**P0/P1 修复**

| 项 | 修复 |
| --- | --- |
| P0 输出根删除任意目录 | `build_package` 只接受 `paths.delivery_root`；移除 CLI `--out`；输出/临时/备份/attempt 路径拒绝链接 |
| P1 主题片审批 | 写入与读取两端都用 `is_named_approver`，要求 `stage=release`；`owner` 与 `review` 阶段都被拒绝 |
| P1 旧机器审批 | `assert_approved` 读取时拒绝非具名 `approved_by`；旧 `"human"` 授权不再生效 |
| P1 先写后拒 | `accept_content`/`accept_artifact`/`accept_subtitles` 先验证审批人，再用临时文件 + `os.replace` 写入 |
| P1 分镜门禁链接 | `is_course_lesson` 改词法包含；`lessons/<slug>` 为 junction 时仍要求签字 |
| P1 分镜证据自报 | 要求从质量报告 Q5 的 `storyboard_signoff` 事实推导；复算具名签字人、lesson、逐页 approve、页面/决策哈希与 schema |
| P1 过期哈希 | 从 approval payload 删除 `quality_report_sha256`；内容哈希是唯一稳定绑定 |
| P1 异常队列 | 选择条目前合并 legacy 同 check 条目；保留 owner/reason/clear_when；写后验 observation 顺序；读取/写入拒绝链接；唯一临时文件；跨进程锁 |
| P2 exclude 前缀 | 按路径组件边界匹配；先检测链接再排除 |

**schema 2 与全链**

- `quality-report`、`certificate`、approval 与 package manifest 都是 schema 2；schema 1 明确报“历史记录，需重新生成/重签/重打包”。
- 合成课程的真实全链测试：`run_release_check`（真实 media QC/字幕 QC/gate/证书）→ `release-approve` review → release → `package` → `package-verify`，全部在临时内容根中完成，`verify_package == []`。
- junction 用例在 Windows 上创建失败时直接失败，不再 skip。

**最终 dev 回归**

```
check log: %TEMP%/CourseWorkspace/state/last-check.log
check summary: checks=50 failed=0 content_exceptions=1
check ok

CourseControl: Ran 892 tests ... OK (skipped=52; 41 are local-course tests not configured in dev)
ModelingStudio 33 · ai_runtime 50 · ContentQA 25 · ManimSandbox 18 · KnowledgeStudio 40
git diff --check HEAD -> clean
production content root -> unchanged (directories, queues, logs, audit cache)
```

`checks=50` 而非 53：`evidence paths` 是生产证据检查，在 dev 根无证据可核；`book index`/`golden` 依赖真实内容根，在 dev 根不存在。三项都打印为 skip，不写成通过。

**仍未关闭**

- `t1-01` 生产内容根的异常仍为 `incomplete`，owner 未具名；dev 回归的异常只写开发根。
- `deliver/` 旧包（10 个 schema 1、2 个无 schema、5 个无 manifest）是历史记录，需单独重打包才能通过新 `package-verify`；本轮未迁移、未改动。
- 旧 `"human"` 审批需具名重签后才能再次发布。
- `check.ps1` 的 50 项检查中，真实内容相关项在 dev 模式显式跳过；生产检查需单独执行。
- C 与边界修复均未提交，等复核。
