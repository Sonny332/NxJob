# AGENTS.md

除必要代码，使用中文交流。结论前置，后补充理由和分析。

- 每次发布前应有固定 checklist，避免忘记同步 README、LICENSE、tag、release、安装包。
- 重大产品语义改变，例如“取消轮次概念”，要主动检查所有 UI 文案和状态模型。
- 桌面版和浏览器版数据不同源，应尽早明确测试环境。
- 每次生成安装包后，应记录测试结果和版本差异。
- 对小白用户，应该默认只暴露安装包，不暴露源码和开发脚本。

## NxJob Project Rules

- MVP Windows-first, but core business code must remain platform-neutral.
- OS-specific behavior may only appear in packaging, path adapter, service startup adapter, and document validation adapter modules.
- Phase 1 uses REST only. Do not implement an MCP server in Phase 1.
- User confirmation is mandatory for application submission and form filling.
- Do not implement bulk scraping, automatic submission, CAPTCHA bypass, or no-confirmation mass applying.
- Before writing or changing UI, read and follow `docs/design.md`.

