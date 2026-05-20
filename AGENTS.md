# AGENTS.md

除必要代码，使用中文交流。结论前置，后补充理由和分析。

- 每次发布前应有固定 checklist，避免忘记同步 README、LICENSE、tag、release、安装包。
- 重大产品语义改变，例如“取消轮次概念”，要主动检查所有 UI 文案和状态模型。
- 桌面版和浏览器版数据不同源，应尽早明确测试环境。
- 每次生成安装包后，应记录测试结果和版本差异。
- 对小白用户，应该默认只暴露安装包，不暴露源码和开发脚本。
- NxJob 是个人 MVP 项目。产品和交付节奏应服务于真实投递闭环，但默认开发流程与 workflow 主规则以 Agent Collaboration Model 为准，不能再让“个人 MVP / 轻量化”覆盖 required sub-agent gates。
- 开发协作、agent 使用、worktree 门槛、PR 粒度和 token efficiency 规则见 `docs/development-governance.md`。涉及这些规则变更时，先读该文档和相关专项文档。
- 默认使用 Agent Collaboration Model：由 Main Controller / PM Agent 管理 sub-agent 工作流；仅在用户人工明确指定当前任务不需要 sub-agent 时，才可脱离该默认流程。
- 涉及业务代码、调试、测试、release、schema、插件 UI、隐私边界或包装脚本的任务，至少需要 Implementer / Coding Agent 和 Reviewer / Evaluator Agent 参与；Reviewer 未完成不得被视为验收通过。

## NxJob Project Rules

- MVP Windows-first, but core business code must remain platform-neutral.
- OS-specific behavior may only appear in packaging, path adapter, service startup adapter, and document validation adapter modules.
- Phase 1 uses REST only. Do not implement an MCP server in Phase 1.
- User confirmation is mandatory for application submission and form filling.
- Do not implement bulk scraping, automatic submission, CAPTCHA bypass, or no-confirmation mass applying.
- Before writing or changing UI, read and follow `docs/design.md`.
- Windows packaging scripts must be tested with install paths containing spaces, such as `%LOCALAPPDATA%\NxJob\LocalService` under `C:\Users\Sonny Shen`.
- When writing commands or scripts that receive Windows paths, use quoted path values, PowerShell `-LiteralPath`, and argument arrays or structured parameters. Do not concatenate path-valued arguments into one shell string.
- Do not pass path-valued arguments through a manually joined `Start-Process -ArgumentList` string. Prefer installed packages, environment variables, splatted argument arrays for direct invocation, or a tested escaping helper.
- Local service startup must not depend on `uvicorn --app-dir <path with spaces>` in background mode; use the venv-installed `nxjob` package so user profile paths are not parsed as CLI arguments.
- Long-running Codex work must use bounded waits. If the UI appears stuck, refresh the session view once, inspect command/sub-agent status, and continue or close stale agents instead of waiting indefinitely.
- When reporting sub-agents in branch details or handoff summaries, include nickname, assigned role, exact model version, reasoning effort, and current state. If the tool cannot confirm the exact model, report `unknown, not acceptable for required gate` and retry with explicit model selection when the gate is mandatory.
- If a required sub-agent fails, times out, or is closed, summarize the cause and mitigation. Treat this as Agent Collaboration Model exception handling, not as a way to relax mandatory gates. Repeated sub-agent failures of the same class must be recorded in development memory; if the same failure happens twice or more, add the mitigation to `docs/development-governance.md`. If the same sub-agent or same class of sub-agent fails 3 consecutive times on the same task and same blocker, PM / Controller may decide that PM Agent directly resolves only that blocker; after the blocker is resolved, return to the required sub-agent workflow and do not treat this as a standing exemption.
