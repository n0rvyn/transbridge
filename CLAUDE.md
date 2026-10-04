# Transbridge

新会话先读 [Transbridge 文档入口](docs/README.md)，再读 [AGENTS.md](AGENTS.md)。本机继续开发时，可另读 `logs/handoffs/HANDOFF-2026-10-02-1731.md`；它是忽略的私人历史日志，不是发布文档，其他机器不保证存在。

公开文档在 `docs/` 维护。真实账号验证、会话交接与安装诊断放在忽略的 `logs/`；不分发这些日志，不把旧交接状态当作当前验证结论。

本机规则入口为根目录 `AGENTS.override.md`（若存在先读），其中要求读取公开 `AGENTS.md`，再遵守本机账号限制。它被 Git 忽略且不进入发布包；其他机器缺少该文件时不能沿用开发账号授权，需核对当前用户明确授权的账号。
