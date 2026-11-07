# shared/ai_runtime

本机 AI 运行时：跨进程锁、单一模型服务生命周期、任务记录、上下文预算。纯标准库实现。

- 需求：`docs/PRD.md` FR-09 / FR-10 / FR-11
- 架构：`docs/ARCHITECTURE.md` §5

## 为什么需要

本机所有项目共享一个 8080 llama.cpp 服务。进程内锁无法约束多个 Agent/项目，因此用**文件锁 + 原子创建**做跨进程互斥；服务只由持锁进程启动，且只停止自己启动的实例。

## 用法

```python
from ai_runtime import ContextBudget, FileLock, ModelSpec, ServerConfig, model_service

server = ServerConfig(executable=r"<AI_ROOT>/bin-sycl/llama-server.exe", port=8080)
model = ModelSpec(key="planner", alias="Qwen3-30B-A3B-Instruct-2507", args=[...], context=32768)
lock = FileLock(workspace / "runtime/locks/llama-8080.lock", task_id="my-task", timeout_s=3600)

with model_service(server, model, lock, log_path):
    ...  # 8080 已就绪且别名匹配，锁由本进程持有
```

```python
budget = ContextBudget(limit=32768, reserved_output=3000)
budget.check(messages, images=[(1280, 720)])   # 超限抛 ContextOverflow
```

```python
store = TaskStore(workspace / "runtime/tasks")
record = TaskRecord(task_id="t1", task_type="modeling.plan", assigned_model="qwen3")
store.run(record, lambda: {"output_artifacts": ["model_plan.json"]})
```

## 本地优先与远程回退

```python
from ai_runtime import FileLock, ModelSpec, RemoteConfig, ServerConfig, route_model

remote = RemoteConfig(
    enabled=True,
    provider="deepseek",
    base_url="https://api.deepseek.com/v1",
    model="deepseek-flash",
    api_key_env="DEEPSEEK_API_KEY",
    supports_vision=True,
    vision_model="deepseek-flash",
)
with route_model(server, model, lock, log_path, remote=remote) as route:
    print(route.provider, route.model)   # local / remote，实际模型
    # 把 route.provider 与 route.model 写入任务记录
```

- 本地 8080 始终先尝试；`busy` / `start_error` / `lock_timeout` / `missing_executable` 才按 `fallback_on` 回退。
- 远程路由不持有本地锁；`provider=remote` 不得写成 `local`。
- key 只从环境变量读取；`health()` 输出不含密钥。
- 视觉阶段只有 `supports_vision=true` 且配置 `vision_model` 才回退。
- 任务记录新增 `provider` 字段（`local` / `remote`）。
- **DeepSeek 固定 `deepseek-flash`；`deepseek-v4-pro` 在 `RemoteConfig` 构造时直接拒绝。**

## 锁语义

- 获取：`O_CREAT | O_EXCL`；内容为 `pid`、`task_id`、`host`、时间戳。
- 等待：轮询到 `timeout_s`，超时抛 `LockTimeout`。
- 陈旧回收：持有者 PID 不存在或超过 `stale_after_s` 时回收。
- 释放：仅当锁内的 PID 与 task_id 匹配当前持有者；不会误删他人锁。
- 异常/Ctrl-C：上下文管理器 `finally` 释放。

## 服务语义

1. 健康且别名匹配 → `reused`；
2. 端口被占用但别名不符 → 等待，仍不符 → `ServerBusy`（blocked），不杀进程；
3. 端口空闲 → 启动 → 健康且别名匹配 → `started`；
4. 结束只停止自己启动的实例，并等待端口释放。

## 任务状态

`pending` / `running` / `completed` / `failed` / `blocked` / `needs_review` / `skipped`。
记录字段与 JSON Schema 见 `ai_runtime.tasks.schema()`；每次写入是原子替换。

## 上下文预算

CJK 字符 1 token，其他字符 4 字符 1 token；图片按像素/750 估算并支持最小 token 下限。
分档：`16K` 默认、`32K` 复杂、`64K` 硬上限。超限抛 `ContextOverflow`，禁止静默截断。

## CLI

```powershell
uv run --project shared/ai_runtime ai-runtime status
uv run --project shared/ai_runtime ai-runtime tasks --root runtime/tasks
uv run --project shared/ai_runtime ai-runtime unlock --lock runtime/locks/llama-8080.lock
uv run --project shared/ai_runtime ai-runtime schema
```

## 测试

```powershell
uv run --project shared/ai_runtime python -m unittest discover -s shared/ai_runtime/tests -t shared/ai_runtime
```

包含真实多进程串行测试（两个子进程竞争同一把锁）、mock HTTP 服务测试，以及本地繁忙 → 远程回退测试。
