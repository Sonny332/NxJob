# AGENTS.md

## 交流与基本原则

除必要代码外使用中文交流。结论和推荐下一步前置，理由和分析后置。

- NxJob 是个人 MVP，开发优先服务真实投递闭环，但不得弱化安全、隐私、Review 或 release gate。
- `docs/development-governance.md` 是完整治理 source of truth；本文件只是 Codex 执行摘要。
- 普通任务读取本文件和 1 份直接相关专项文档；高风险或跨域任务再读取治理文档和 1–2 份专项文档。
- 不重复扫描无关文件，不创建无明确收益的 Agent、worktree 或 PR。

## 产品、安全与隐私红线

- MVP Windows-first，但核心业务代码必须 platform-neutral；OS 特定行为只允许位于 packaging、path adapter、service startup adapter 和 document validation adapter。
- Phase 1 只使用 REST，不实现 MCP server。
- 表单填写与投递必须经过用户确认。
- 禁止 bulk scraping、automatic submission、CAPTCHA bypass 和 no-confirmation mass applying。
- 真实简历、数据库、投递记录、凭据和完整 PromptLog 不得进入 Git、发布包、普通日志或插件可见错误。
- 修改 UI 前读取 `docs/design.md`；桌面版和浏览器版数据不同源时先明确测试环境。

## 任务分类与最低 Gate

不明确满足低一级条件时，使用更高 gate。完整触发条件见 `docs/development-governance.md`。

| 分类 | 最低 Gate |
| --- | --- |
| Controller-direct | 仅限无运行时、测试、用户可见、合同或治理语义变化的闭合 allowlist |
| Implementer | GPT-5.4 / Medium；局部、行为保持或明确复现的单模块工作，且无 Reviewer 强制触发 |
| Implementer + Reviewer | GPT-5.4 / Medium Implementer + 独立 GPT-5.6 Terra / High Reviewer；适用于用户能力、UI 状态、API/schema/data、隐私、安装/路径/进程、扩展权限、弱化测试、跨模块不确定性及关键治理语义 |
| Planner + Implementer + Reviewer | GPT-5.6 Sol / High Controller、Planner、Reviewer + GPT-5.4 / Medium Implementer；适用于架构、迁移、跨子系统、核心边界、权限/治理来源、难回滚或方案不清 |

任何 condition、default、return、exception、assertion、fixture、mock、path、argument、用户可见含义或产品规则变化都不属于 Controller-direct。

正式发布顺序：Implementer → Release Agent → independent Reviewer → Controller recommendation → 用户明确授权远程发布。

## 强制模型

| Role | 普通任务 | 架构 / 重大影响任务 |
| --- | --- | --- |
| Controller | GPT-5.6 Terra / High | GPT-5.6 Sol / High |
| Planner / Architect | GPT-5.6 Terra / High | GPT-5.6 Sol / High |
| Reviewer / Evaluator | GPT-5.6 Terra / High | GPT-5.6 Sol / High |
| Implementer | GPT-5.4 / Medium | GPT-5.4 / Medium |
| Release Agent | GPT-5.4 / Medium | GPT-5.4 / Medium |
| Test Agent | GPT-5.4 / Medium | GPT-5.4 / Medium |
| Code Mapper | GPT-5 mini / Low | GPT-5 mini / Low |
| Docs Agent | GPT-5 mini / Low | GPT-5 mini / Low |
| Form Answer Agent | GPT-5 mini / Medium | GPT-5 mini / Medium |
| Resume Quality Agent | GPT-5.6 Terra / High | GPT-5.6 Sol / High |

模型和 reasoning effort 是硬要求，不得静默替换或降级。一次定向重试后仍不可用即停止并交还用户。

## Sol / Worktree / PR 硬触发摘要

- Sol：架构或职责重分、迁移与既有数据兼容、新 provider/platform/persistence/data source、核心技术或隐私/确认/自动化边界、治理模型/权限/source-of-truth、方案不清或难回滚。
- Worktree：上述重大改变、正式 release candidate、并行 Implementer、互斥实验、两个以上独立运行时子系统、无法单次 revert、安全上不能共享的脏工作区或用户明确要求。
- PR：架构/迁移、隐私安全边界、正式 release candidate、跨运行时子系统、核心 API 或插件/服务合同、高回滚风险、需要远程 review 历史或用户明确要求。
- 仅仅使用 Implementer 或 Reviewer 不会自动触发 worktree 或 PR。

## Execution Lane 与生命周期

- Default active lane 为 1，hard max 为 2，`max_threads = 2`，max depth 为 1。
- 仅独立、不重叠、无顺序依赖且明显缩短工期时使用两条 lane；外部 worker 与原生 Agent 共用预算。
- Required role 最多两次启动：一次正常尝试和一次定向重试。
- Implementer–Reviewer 最多初审加两轮修复/re-review。
- Planner、Mapper、Docs、Test、Release Agent 的输出被接收后关闭；Implementer 保留到 Reviewer 反馈完成。
- 未确认关闭标记为 `stale — closure unconfirmed`，不得算作 gate pass。
- Code Mapper、Test Agent、Docs Agent 是按条件启用的可选角色，不是默认 gate；external worker 是 default-off auxiliary worker，不能替代必需角色。

## Git、命令与用户授权

- 可自主执行：读取/搜索、既有检查、`git status/diff/log/fetch`、只读远端比较、合格的本地 branch/worktree/commit、短时本地 build/service/package 检查及清理本任务临时产物。
- 必须用户明确授权：`pull`、merge、rebase、破坏性 reset/checkout、删除未合并 branch/worktree、依赖与全局环境变更、真实数据操作、sandbox 外命令（已批准的精确 pytest wrapper 除外）以及任何远程写入。
- push、tag、PR/Release 创建或更新、artifact upload 始终需要用户授权；`fetch` 可自主执行。
- 永不使用管理员/UAC/system 权限，不扩大 ACL，不测试真实私有数据，不静默上传数据。
- Windows 路径使用引号、PowerShell `-LiteralPath`、参数数组或结构化参数；不得手工拼接 path-valued shell 参数。

## 文档路由

| 领域 | 读取 |
| --- | --- |
| 治理、gate、model | `docs/development-governance.md` |
| UI | `docs/design.md` |
| API | `docs/api-schema.md` |
| Data model | `docs/data-model.md` |
| 隐私、安全、确认 | `docs/privacy-boundary.md` |
| Windows 测试 | `scripts/run_pytest.ps1`、`scripts/test-local-service.ps1` 及专项测试规则 |
| 安装与路径 | `docs/install-windows.md` |
| Release | `docs/release-checklist.md`、`docs/release-hardening.md`、`docs/versioning.md` |
| External worker | `CLAUDE.md`、approved task packet、`docs/multi-agent-development.md` |
| 仓库结构 | 实际文件树优先，`docs/project-structure.md` 仅作说明/目标 |

## Windows 测试摘要

- Python 测试使用 `scripts/run_pytest.ps1` 或 `scripts/test-local-service.ps1`，不先运行 raw pytest。
- 遇到已知 pytest ACL 权限失败后停止重复相同命令。
- 仅对精确 wrapper 命令申请 sandbox exception，始终保持普通非管理员用户。
- 禁止 UAC、管理员或 system 执行及任何全局或递归 ACL 扩大。
- 报告实际 wrapper 命令、sandbox 状态、非管理员状态、pass/fail 数和临时目录处理状态。

## 最终 Handoff

固定字段：Status、完成目标与范围、修改文件、实际验证和结果、未验证项及理由、风险/阻塞、branch/worktree/commit/push 状态、下一建议动作。

按条件补充：Agent nickname、role、exact model、reasoning effort、state、输出是否采用、retry/stale 状态、Reviewer 决定、release 证据、用户授权状态和 Interruption Checkpoint。无法确认必需模型时写 `unknown, not acceptable for required gate`。
