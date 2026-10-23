# Transbridge 项目文档

Transbridge 是项目与 marketplace，Garminops 是 Garmin 插件及同名 skill；当前为桌面本地开发插件。

## 公开文档

- [运行、登录、测试与打包](operations/RUNNING.md)
- [错误诊断契约](operations/ERROR_DIAGNOSTICS.md)
- [范围与已知问题](scope/SCOPE.md)
- [能力清单](scope/CAPABILITY_INVENTORY.md)
- [上游方法索引](research/SOURCE_METHODS.md)
- [Web 协议研究](research/WEB_CONTRACT_RESEARCH.md)
- [能力清单数据](research/inventory.json)
- [来源记录](research/sources.json)
- [验证范围与限制](validation/LIVE_VERIFICATION.md)
- [读取兼容性概况](validation/READ_VERIFICATION.json)
- [数据判断规则](validation/TASK_VALIDATION.md)
- [桌面验收方法](validation/DESKTOP_EVAL.md)

公开文档保留使用说明、判断方法、契约与能力边界。真实验证流水、个人响应摘要、覆盖报告、会话交接及安装调试记录保存在开发根目录被忽略的 `logs/`，不跟踪、不随发布包分发；新的使用者不能依赖这些本机文件。

开发规则见根目录 `AGENTS.md`；技能说明见 [Garminops](../garminops/skills/garminops/SKILL.md)。协议测试、真实业务、宿主发现和当前聊天验收是不同证据，不能相互替代。公开分支已采用清理后的初始历史；旧开发历史的备份仅保留在本地，不随公开分支或插件分发。
