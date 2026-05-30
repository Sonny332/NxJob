# NxJob Product Blueprint

## Product Principle

NxJob 的目标不是替用户自动求职，而是把求职中高频、低价值、重复性的操作下沉到本地运行层；把语义复杂、需要判断和表达质量的任务交给 AI；把用户动作压缩到浏览、点击、审核、确认。

早期 NxJob 不重复建设招聘网站和 LinkedIn Premium 已经做好的判断能力。平台已有的匹配度、简历建议、面试建议可以先作为外部智能来源使用。NxJob 负责记录这些判断、用户决策和最终结果，并在数据积累后，把稳定逻辑逐步固化到本地运行层或 AI 层。

NxJob 要具备自学习、自迭代属性。它不应只记录“投了什么岗位”，还要持续记录“为什么投、参考了什么判断、使用了哪个 resume 版本、后续是否收到回复、哪些搜索词和岗位类型更有效”。这些反馈会逐步反哺搜索策略、匹配判断、resume tailor、表单填写和面试准备，让系统从用户的真实求职结果中变得更贴合个人。

核心设计原则：

- 用户层优先减少动作：默认只要求用户浏览、点击、审核、确认。
- 本地运行层优先固化流程：能用规则、缓存、模板、数据库解决的问题，不优先消耗 AI token。
- AI 层优先处理复杂语义：岗位理解、表达改写、策略复盘、面试演练等不稳定问题交给 AI。
- 外部智能优先复用：早期充分利用 LinkedIn Premium、Indeed 和 ATS 页面已有信息，不重复造轮子。
- 反馈数据优先沉淀：每次捕获、判断、tailor、投递、回复和面试都应成为后续优化依据。
- 用户确认不可跳过：NxJob 可以辅助填写和建议操作，但不自动提交、不绕过验证、不进行无确认群投。

## Diagram Rule

NxJob 后续所有流程图默认分层绘制，必须明显区分用户层、本地运行层、AI 层。

- 用户层：用户可见、需要用户判断或确认的动作，例如浏览、点击、审核、提交。
- 本地运行层：可固化、可缓存、可测试、可复用的流程，例如页面读取、清洗、去重、模板渲染、数据库记录、文件生成、状态流转。
- AI 层：处理不确定语义和表达质量的问题，例如 JD 解析、匹配判断、resume tailor、复杂表单语义映射、搜索策略复盘、面试预演。

流程图规则：

- 每张流程图都用 `subgraph` 或等价结构拆出三层。
- 用户确认动作必须留在用户层。
- 本地可规则化的动作不得默认画进 AI 层。
- AI 输出必须回到本地运行层记录，再交给用户层审核。
- 外部平台智能，例如 LinkedIn Premium 建议，作为用户层可见输入或本地层记录来源，不视为 NxJob 内部 AI 能力。

## Architecture

NxJob 采用浏览器插件加本地服务的轻量架构。浏览器插件贴近网页，负责用户入口和页面交互；本地服务负责稳定流程、文件生成、数据库、AI 编排和可迭代记录。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["招聘网站页面<br/>LinkedIn / Indeed / ATS"]
    U2["NxJob 插件入口<br/>Popup / Side Panel / Overlay"]
    U3["用户审核<br/>Apply / Skip / Tailor / Fill / Track"]
    U4["外部平台智能<br/>LinkedIn Premium / Indeed 提示"]
  end

  subgraph Local["本地运行层"]
    L1["Extension Content Script<br/>读取选中文本和页面结构"]
    L2["Local API Service<br/>统一入口"]
    L3["Workflow Orchestrator<br/>流程编排"]
    L4["Rule Engine & Cache<br/>去重 / 状态 / sponsorship 规则"]
    L5["Resume Renderer<br/>DOCX / PDF / 页数检查"]
    L6["Form Assistant Runtime<br/>字段识别 / 草稿填入"]
    L7["SQLite + File Store<br/>JD / Application / Resume Version / Logs"]
    L8["Email Sync<br/>求职邮箱同步和规则分类"]
  end

  subgraph AI["AI 层"]
    A1["AI Provider Adapter"]
    A2["JD Analyst"]
    A3["Resume Tailor"]
    A4["Form Semantics Mapper"]
    A5["Search Strategy Optimizer"]
    A6["Interview Coach"]
  end

  U1 --> U2
  U4 --> U2
  U2 --> L1 --> L2 --> L3
  L3 --> L4
  L3 --> L5
  L3 --> L6
  L3 --> L7
  L3 --> L8
  L3 --> A1
  A1 --> A2
  A1 --> A3
  A1 --> A4
  A1 --> A5
  A1 --> A6
  A2 --> L7
  A3 --> L5
  A4 --> L6
  A5 --> L7
  A6 --> L7
  L5 --> U3
  L6 --> U3
  L7 --> U3
```

## Workflow

### Workflow 1: Capture JD and Decide

目标：用户在招聘网站正常浏览，NxJob 只在用户主动点击后捕获 JD、记录平台判断，并补充 sponsorship 检查。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["浏览岗位"]
    U2["查看平台匹配度和建议"]
    U3["选中 JD / 点击 Capture"]
    U4["审核 NxJob 判断"]
    U5["Apply / Skip / Later"]
  end

  subgraph Local["本地运行层"]
    L1["读取选中文本和页面 URL"]
    L2["清洗 JD / 提取基础字段"]
    L3["记录平台建议和用户上下文"]
    L4["去重 / 查历史记录"]
    L5["sponsorship 规则检查"]
    L6["保存 JobLead 和判断证据"]
  end

  subgraph AI["AI 层"]
    A1["缺失字段补全"]
    A2["复杂 sponsorship 语义判断"]
    A3["可选匹配度补充分析"]
  end

  U1 --> U2 --> U3
  U3 --> L1 --> L2 --> L3 --> L4 --> L5
  L5 --> A1
  L5 --> A2
  L4 --> A3
  A1 --> L6
  A2 --> L6
  A3 --> L6
  L6 --> U4 --> U5
```

### Workflow 2: Tailor Resume

目标：让 resume tailor 在一到两分钟内完成。AI 负责内容选择和表达，本地层负责证据准备、模板渲染、页数检查和版本记录。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["点击 Tailor Resume"]
    U2["审核生成结果"]
    U3["确认使用 / 重新生成 / 手动修改"]
  end

  subgraph Local["本地运行层"]
    L1["加载 JD Snapshot"]
    L2["加载 Master Resume / Evidence Bank"]
    L3["读取历史成功版本和岗位类型"]
    L4["构造最小 AI 输入"]
    L5["渲染 DOCX / PDF"]
    L6["页数检查 / 文件命名"]
    L7["保存 Resume Version 和 Prompt Log"]
  end

  subgraph AI["AI 层"]
    A1["选择最相关证据"]
    A2["改写 Summary / Bullets / Skills"]
    A3["输出结构化 Resume JSON"]
  end

  U1 --> L1 --> L2 --> L3 --> L4
  L4 --> A1 --> A2 --> A3
  A3 --> L5 --> L6 --> L7
  L7 --> U2 --> U3
```

### Workflow 3: Apply Assistant and Tracking

目标：降低非 Easy Apply 表单填写成本，但保留用户最终确认，不自动提交。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["打开外部 ATS 表单"]
    U2["点击 Fill Assist"]
    U3["审核字段填充草稿"]
    U4["用户手动提交"]
    U5["确认投递状态"]
  end

  subgraph Local["本地运行层"]
    L1["读取表单 DOM 和字段标签"]
    L2["匹配本地 Profile Vault"]
    L3["套用域名级字段缓存"]
    L4["生成填充草稿"]
    L5["写入页面字段"]
    L6["记录 Application / Resume Version / Form Snapshot"]
  end

  subgraph AI["AI 层"]
    A1["复杂字段语义映射"]
    A2["开放问题回答草稿"]
    A3["缺失信息风险提示"]
  end

  U1 --> U2 --> L1 --> L2 --> L3
  L3 --> A1
  L3 --> A2
  L3 --> A3
  A1 --> L4
  A2 --> L4
  A3 --> L4
  L4 --> U3 --> L5
  L5 --> U4 --> U5 --> L6
```

### Workflow 4: Success Feedback Loop

目标：把已经获得 screen / recruiter reply / interview 的岗位和对应 resume 版本沉淀为未来 tailor 的高价值参考，而不是只把它们当作普通投递记录。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["收到 screen / recruiter reply"]
    U2["标记为 Positive Reply"]
    U3["补充备注<br/>为什么这个岗位可能有效"]
    U4["未来 Tailor 时审核成功参考"]
  end

  subgraph Local["本地运行层"]
    L1["定位 Application 记录"]
    L2["关联 Job Snapshot"]
    L3["关联投递时使用的 Resume Version"]
    L4["记录 Outcome Signal"]
    L5["提取可复用特征<br/>岗位类型 / 搜索词 / 技能关键词 / bullet 组合"]
    L6["更新 Success Reference Bank"]
    L7["未来 Tailor 时优先检索相似成功案例"]
  end

  subgraph AI["AI 层"]
    A1["分析成功岗位共性"]
    A2["总结有效表达方向"]
    A3["给出未来 resume tailor 参考建议"]
  end

  U1 --> U2 --> U3
  U2 --> L1 --> L2 --> L3 --> L4 --> L5 --> L6
  L6 --> A1 --> A2 --> A3
  A3 --> L7 --> U4
```

成功反馈应至少记录：

- 原始 JD snapshot。
- 投递时使用的 resume version。
- 使用的搜索词或来源路径。
- 平台匹配度、LinkedIn Premium 建议或用户当时的判断。
- 是否支持 sponsorship，以及当时的判断依据。
- 投递日期、回复日期、回复类型。
- 哪些 bullet、技能关键词、项目经历可能促成回复。
- 用户复盘备注。

这些记录会进入 `Success Reference Bank`。未来 resume tailor 时，本地运行层先检索相似成功案例，再把最相关的成功参考压缩后交给 AI 层使用，避免每次都从零判断，也避免无节制增加 token。

## MCP / Skill Strategy

NxJob 会把 `Analyze Sponsorship`、`Tailor Resume`、`Fill Form Answer from Master Resume Bullets` 设计成插件里的一键能力，但首版不要求浏览器插件直接成为 MCP client。插件负责触发和展示，本地服务负责稳定执行和记录，AI 层只处理复杂语义和表达改写。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["插件按钮<br/>Analyze Sponsorship"]
    U2["插件按钮<br/>Tailor Resume"]
    U3["插件按钮<br/>Fill Form Answer"]
    U4["用户审核结果"]
  end

  subgraph Local["本地运行层"]
    L1["NxJob Local Service"]
    L2["sponsorship_analyzer workflow"]
    L3["resume_tailor workflow"]
    L4["form_answer_drafter workflow"]
    L5["cache / db"]
    L6["docx renderer"]
    L7["success reference bank"]
    L8["profile vault / master resume bullets"]
    L9["REST API<br/>MCP-compatible schema"]
    L10["Future MCP Server"]
  end

  subgraph AI["AI 层"]
    A1["sponsorship 复杂语义判断<br/>JD 不明确时结合公开信息"]
    A2["resume 内容选择与改写"]
    A3["表单问题答案草稿"]
  end

  U1 --> L9 --> L1 --> L2
  U2 --> L9 --> L1 --> L3
  U3 --> L9 --> L1 --> L4
  L2 --> L5
  L3 --> L5
  L3 --> L6
  L3 --> L7
  L4 --> L8
  L2 --> A1 --> L5
  L3 --> A2 --> L6
  L4 --> A3 --> L5
  L5 --> U4
  L6 --> U4
  L7 --> L3
  L8 --> L4
  L2 --> L10
  L3 --> L10
  L4 --> L10
```

分阶段策略：

- Phase 1：插件做三个一键按钮；本地服务实现三个稳定 workflow；接口先用 REST；schema 按 MCP tool 的输入输出标准设计。
- Phase 2：同一套 workflow 暴露为 MCP tools：`analyze_sponsorship`、`tailor_resume`、`draft_form_answer_from_resume_bullets`。
- Phase 3：插件可以选择继续走 REST，或者变成 MCP client；外部 AI 客户端也可以调用 NxJob MCP server。

首版固定能力：

- `Analyze Sponsorship`：判断岗位是否支持 sponsorship，输出状态、证据、置信度、风险提示、需要确认的问题。
- `Tailor Resume`：基于 JD、master resume、success reference bank 生成定制 resume，并记录 resume version、选用证据、变更摘要和文件路径。
- `Fill Form Answer from Master Resume Bullets`：根据当前表单问题、JD、master resume bullets 和 profile vault 生成答案草稿，用户审核后填入当前字段。

设计约束：

- 插件按钮属于用户层，只负责触发、展示和确认。
- 本地服务属于本地运行层，负责 workflow、缓存、数据库、文件生成、日志和后续 MCP 暴露。
- AI 层只负责 sponsorship 复杂语义判断、resume 内容选择与改写，以及复杂表单问题答案草稿。
- REST 接口的输入输出 schema 要尽量接近未来 MCP tool schema，避免 Phase 2 重写业务逻辑。
- MCP 化不能改变安全边界：仍然不自动提交、不绕过验证、不无确认群投。

## Sponsorship Evidence Strategy

Sponsorship 判断分两阶段处理：JD 明确时优先用本地规则；JD 不明确时，才由 AI 结合公开信息做概率判断。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["点击 Analyze Sponsorship"]
    U2["查看状态 / 证据 / 风险提示"]
    U3["确认是否继续投递"]
  end

  subgraph Local["本地运行层"]
    L1["读取 JD Snapshot"]
    L2["本地规则检查<br/>will sponsor / will not sponsor / work authorization"]
    L3["公司名称规范化"]
    L4["查询本地 sponsorship cache"]
    L5["查询公开数据连接器<br/>公司官网 / 政府公开数据 / 历史记录"]
    L6["保存判断证据和来源"]
    L7["输出 sponsorship_status"]
  end

  subgraph AI["AI 层"]
    A1["仅在 JD 不明确时调用"]
    A2["综合公开信息判断可能性"]
    A3["输出 probability / confidence / evidence / caveats"]
  end

  U1 --> L1 --> L2
  L2 --> L7
  L2 --> L3 --> L4 --> L5
  L5 --> A1 --> A2 --> A3 --> L6 --> L7
  L7 --> U2 --> U3
```

Sponsorship 状态只能表达求职决策风险，不表达法律结论：

- `supports`：JD 或可信来源明确支持。
- `does_not_support`：JD 或可信来源明确不支持。
- `likely_supports`：公开信息显示该公司有较强 sponsorship 历史，但当前岗位未明确。
- `likely_not_supports`：公开信息或岗位条件显示支持概率较低，但当前岗位未明确拒绝。
- `needs_confirmation`：需要向 recruiter 或申请表继续确认。
- `unknown`：证据不足。

MVP 判断优先级：

1. 当前 JD 或申请表中的 role-specific 明确政策，例如 `not eligible for visa sponsorship` 或 `sponsorship is available for this role`。
2. 申请表筛选语句，例如 `authorized to work without sponsorship now or in the future`。
3. 泛化 work authorization 语句，例如 `authorized to work in the United States`。这类语句只能触发确认，不能直接等同于不支持 sponsorship。
4. 公司政策、历史投递、政府公开数据或第三方聚合数据。这些信息只能作为概率证据，不能覆盖当前岗位的明确拒绝。

公开信息优先级：

- 当前 JD 和申请表原文。
- 公司官网、career page、FAQ。
- 政府公开数据，例如 USCIS H-1B Employer Data Hub、DOL OFLC LCA disclosure data。
- 用户历史投递和 recruiter 回复。
- 第三方聚合数据只能作为辅助线索，不作为确定结论。

后续阶段，当 sponsorship 流程跑成熟后，可以把稳定规则和公开数据查询流程固化为 `analyze_sponsorship` skill / MCP tool。

## Form Answer Drafting Strategy

`Fill Form Answer from Master Resume Bullets` 解决的是非 Easy Apply 表单里的开放问题或半结构化问题，例如 why this company、relevant experience、work authorization explanation、project description、additional information。

```mermaid
flowchart TD
  subgraph User["用户层"]
    U1["聚焦当前表单问题"]
    U2["点击 Fill Form Answer"]
    U3["审核答案草稿"]
    U4["确认填入当前字段"]
  end

  subgraph Local["本地运行层"]
    L1["读取当前字段 label / placeholder / surrounding text"]
    L2["读取 JD Snapshot"]
    L3["读取 Master Resume Bullets"]
    L4["读取 Profile Vault<br/>固定个人信息 / work authorization / location"]
    L5["检索相似问题历史答案"]
    L6["构造最小 AI 输入"]
    L7["缓存答案草稿和用户修改"]
    L8["写入当前字段<br/>不自动提交"]
  end

  subgraph AI["AI 层"]
    A1["理解问题意图"]
    A2["选择相关 bullet 和事实"]
    A3["生成简短、真实、可编辑答案"]
  end

  U1 --> U2 --> L1 --> L2 --> L3 --> L4 --> L5 --> L6
  L6 --> A1 --> A2 --> A3 --> L7
  L7 --> U3 --> U4 --> L8
```

实现原则：

- 优先复用 master resume bullets，不临场编造新事实。
- 常见固定字段走本地 Profile Vault，不消耗 AI token。
- 相同公司或相似问题优先复用历史答案。
- AI 只生成草稿，用户确认后才填入。
- 永远不自动点击 submit。
