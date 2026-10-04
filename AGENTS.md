# Transbridge development rules

This directory is the development root for Codex/ChatGPT plugins and connectors. Garmin Connect is the first connector under investigation.

## Local rules loading

In a source checkout, read `AGENTS.override.md` if it exists and has not already been loaded. It holds private local restrictions, never implicit permission. Codex discovers that override before this file; the local override must read this public file first. If no override or authorized account is available, identify the user-authorized account before business reads/writes. Private rules are ignored and excluded from packages; arbitrary filenames are not automatically loaded.

## User requirements

- Use the four-category policy approved by the user: past facts are read-only; training plans and personal settings are readable/writable; device actions require separate authorization. Reads are allowed across categories.
- The detailed API inventory is an engineering checklist, not a list of per-API permission questions. Technical uncertainty does not revoke an approved capability.
- Garmin recorded activities and other logged data are read-only. Never create/import, edit, delete, or trigger recalculation of logged records through this connector. Activity names, descriptions, types, exercise sets, and gear associations are part of recorded activities.
- Training-plan permission includes creating, editing and deleting templates and calendar schedules. Personal-setting writes must not change historical records. Device delivery is not implied by calendar scheduling.
- Only raise a permission exception when an operation crosses these categories, affects history, or falls outside them. Do not infer approval for unrelated social actions.
- Continue authorized research and preparation without repeated confirmation. Stop for an actual blocker or a decision reserved to the user; do not invent permission decisions.
- Verify identity in the target service. A Chrome profile name is not a Garmin account identity and must never be used to infer an account mismatch or invent a blocker. Match the actual Garmin service identity and region to the account explicitly authorized by the user for this task. Do not read or write other accounts. If the authorized account is not established, obtain identification/authorization before business reads or writes; a saved login is not permission. Once the authorized service account is verified, continue without repeating identity approval. Actual tool denials must be reported accurately, not presented as proof of an account mismatch or bypassed.
- Do not introduce arbitrary processing limits. Identify inherited library limits before selecting the runtime.
- Verify real input samples before building parsers or write payloads. Source code evidence is not live account verification.
- Keep user requirements distinct from AI proposals.

## Current phase

The four-category permission policy is approved. A local development runtime exists; technical write contracts and live compatibility remain to be verified. Read `docs/scope/CAPABILITY_INVENTORY.md`, `docs/scope/SCOPE.md` and `docs/operations/RUNNING.md` before changing connector behavior. Do not label the development read adapters as a finished connector or drop approved write capabilities. Validate garmin.com first, then garmin.cn using the same logic and one active region per connection; no cross-region synchronization.

## AI-proposed engineering controls (not additional product decisions)

- Enforce approved permissions at both named tools and the outbound request boundary. An instruction or MCP annotation alone is insufficient.
- Do not expose arbitrary URLs, HTTP methods, GraphQL documents, or upstream method dispatch as agent tools; these can bypass the permission policy.
- Treat templates, scheduled instances, recorded activities, profile settings, and device settings as separate resources with separate identifiers.
- Validate the account, region, resource, operation, and allowed fields. A configuration endpoint can contain both settings and logged values.
- Preserve unrelated fields when an upstream update replaces an entire object. Read back approved changes through the normal user path before reporting success.
- Never test prohibited writes on real logged data. Test their rejection before network dispatch.
- Do not commit credentials, tokens, personal response dumps, or private exports. Do not reuse Glink credentials implicitly.
- Keep authentication separate from the data-operation policy. Login/session refresh is not a grant to mutate user data.
- Keep Glink and shared Python environments unchanged; they are references, not this project's runtime.

## User scope updates (2026-10-02)

- China-region business validation and Connect+-exclusive features are deferred TODOs, not current-release blockers. Preserve existing regional login; do not relabel ordinary unverified features as paid-only without evidence.
- FTHR null restoration is accepted known issue KI-001. Numeric zero is not equivalent to unset; do not claim null restoration succeeded. The user explicitly ordered no more tests or attempts for this issue. Stop related probing, sentinel writes, clearing and restoration tests unless the user explicitly reopens it. Do not make resolving it a current-release acceptance condition.

## Documentation location

Public project documentation belongs in the project-root `docs/` directory. Private execution logs belong in ignored `logs/`; private local rules belong in ignored `AGENTS.override.md`. Do not move it under a plugin or skill. Plugin packages contain generated documentation copies only.

# Transbridge 项目规则

来源：本会话当前轮用户原话「append this project-wide rules to AGENTS.md and then tell me how to enhance the current use-wide rules.」；权限与边界来自本会话用户提供的 AGENTS.md project-doc。

以下为本项目规则摘要；user-wide 协作规则由用户全局文件维护，不在本文件复制。

## 结构与范围

- Marketplace：Transbridge；插件：Garminops；当前 skill：Garminops。
- 项目文档在根目录 `docs/`，不得放回插件或 skill。修改行为前读 `docs/scope/SCOPE.md`、`docs/scope/CAPABILITY_INVENTORY.md`、`docs/operations/RUNNING.md`。
- 当前交付为桌面本地插件；能力清单是工程检查表，不是逐 API 权限审批或完成声明。
- 保留区域登录，一次连接一个区域，不跨区同步。国区业务验证与 Connect+ 专属能力延期，不阻塞当前交付；无证据不得把普通未验证能力归为付费专属。

## 数据与授权

- 历史事实只读，禁止创建、导入、修改、删除或重算记录。活动名称、描述、类型、训练组和装备关联均属于历史。
- 训练计划允许模板及日历排程的创建、修改、删除；个人设置允许不影响历史的修改。排程不授权设备投递。
- 各类别读取允许；设备动作、跨类别、历史影响和范围外操作单独授权。社交动作不包含在现有授权内。
- 仅使用用户明确授权并经目标服务身份核对的账号和区域；授权账号不明确时，先确认身份与授权再访问业务数据，不从已保存登录推断许可；Chrome profile 不代表 Garmin 身份。账号已验证后不重复索要批准。工具拒绝照实报告，不绕过或解释为账号不符。
- 登录和会话刷新不授予数据修改权限。

## 工程边界

- 权限同时在工具与出站请求边界执行；不暴露任意 URL、方法、GraphQL 或上游 dispatch。
- 区分模板、排程、活动、个人设置、设备设置及其 ID；验证账号、区域、资源、操作和字段。
- 先验证真实样本再写解析和 payload；源码不能替代账户验证。识别上游限制，不引入任意处理上限。
- 整对象更新保留无关字段，通过正常用户路径回读后才报告成功。
- 历史写入只测网络发送前拒绝，不在真实历史上测试。
- 不提交凭证、token、个人响应或私有导出；不借用 Glink 凭证，不改 Glink 或共享 Python 环境。
- 保留用户要求与 AI 提案的区别，不以技术未验证重新打开已批准权限。

## KI-001

FTHR 清空为 null 的契约未解决；数值 0 与未设置不等价，不声称已恢复空值。用户已接受为已知问题，明确停止相关探测、哨兵值、清空、测试和恢复尝试。只有用户明确重开才继续，不作为当前发布验收条件。
