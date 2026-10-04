# Garmin 范围与决策

状态：2026-10-02 用户已同意四类权限；转入技术验证，不再逐 API 等待权限选择。

## 已批准权限

| 类别 | 权限 | 边界 |
| --- | --- | --- |
| 已发生的事实 | 只读 | 活动及其它日志禁止新增、导入、编辑、删除和历史重算；名称、描述、类型、组数、装备关联同样属于历史记录 |
| 训练计划 | 可读写 | 包括训练模板和日历计划的创建、修改、删除、排课、取消与调整 |
| 个人设置 | 可读写 | 包括最大心率、FTHR、区间、目标、默认装备等；不改历史 |
| 设备操作 | 读取允许，动作单独授权 | 发送训练到手表不随日历排课自动获准 |

读取统一允许。历史不可改的硬规则优先于其它授权。按操作实际影响分类，不按 URL、方法名或画面名称分类。

## 原始目标及本次决定

- 此目录作为 Codex/ChatGPT 插件与连接器开发根目录，Garmin 是第一个项目。
- 参考 Python Garmin 库和 Glink，先调查能力，再决定权限。
- 用户最初给出的排课、最大心率、FTHR 是例子，不是完整功能清单。
- 本次四类决策替代此前逐项审批 API 的方式。详细清单只用于开发检查。
- 不改已记录的数据。持续推进已授权工作；只有真实阻碍、跨类别例外或设备动作授权才提出。

## 技术待验证不等于权限待定

最大心率/FTHR 写入、区域差异、真实响应结构、整对象更新和副作用均由工程研究解决。允许的能力在技术未验证时保留，不静默删除或改为只读。

只凭这次分类批准不执行任意真实账号变更。分类决定连接器允许的能力；具体账号操作仍需来自用户任务，设备动作须有单独授权。

区域顺序已定：本轮完整验证 garmin.com；garmin.cn 验证按用户 2026-10-02 决定移至后续 TODO，不阻塞本轮交付。一套逻辑，一次授权并连接一个指定区域；区域域名和会话分开，不做双区同步。本地开发运行环境已建立；目标主机接入与远程部署在对应步骤解决，不重新审查四类权限。

## 局部例外

- 挑战加入/退出属于参与行为，不能直接当作训练计划或个人设置。清单 G38/G39 保留为分类例外；不阻塞其它工作。
- 社交消息、邀请、关注不是个人隐私设置，不因设置可写而授权。
- 历史归档恢复请求需要先验证是否仅恢复读取；不得以读取目的绕过历史不可改规则。
- 配置对象混有日志字段、删除装备涉及过去活动、计划编辑涉及已完成记录时，历史硬规则优先；查清影响后再决定是否需要提出例外。

## ⚠️ AI additions: proposed verification requirements

- Obtain authorized read-only samples for the selected categories in each selected region before defining response models. Distinguish no data from unavailable/unauthorized data.
- Establish max HR/FTHR setting fields independently from historical threshold measurements and daily maximum heart rate. No inference from similar field names.
- For each permitted write, verify exact HTTP method, route, payload, full-object versus partial replacement, and side effects. Do not infer that GET support means PUT support.
- Check logged-data mutation rejection before network dispatch, including arbitrary-path and mixed-object attempts.
- Verify approved writes by reading the changed resource back; verify calendar entries separately from templates. Connect persistence does not prove device synchronization.
- Verify pagination and totals without silently inheriting upstream default page sizes, chart downsampling, month lookahead, or hard loop caps as product limits.
- Cover failed writes, uncertain timeouts, duplicates on retry, stale settings, and ID confusion. Do not retry non-idempotent operations without resolving whether the previous request succeeded.

No authenticated samples were retrieved and no Garmin write was executed during inventory research. Source coverage is recorded separately from live verification.

## 使用端决定（2026-10-02）

用户指定 Codex／ChatGPT 桌面本地插件，沿用本地登录。本次不需要网页版、手机远程服务或云端凭证托管。只运行一个 MCP 服务；成功登录选择当前区域，后续调用跟随该选择。国区仍需自己的真实会话。


## 用户指定的后续 TODO（2026-10-02）

本轮交付及验收范围为国际区 garmin.com 普通账号功能。以下工作由用户明确延期，不作为本轮未完成项；四类权限和历史不可改规则保持有效。

- [ ] 国区 garmin.cn 业务验证：保留已完成的登录与会话恢复能力，后续确认国区测试账号后，再验证读取及计划/设置写入。当前不切换区域或访问国区业务数据。
- [ ] Connect+ 专属功能：后续取得相应账号权益和真实样本，再研究契约、接入并验证。不购买订阅，不要求用户当前开通。普通账号功能不得仅因技术困难被归入此项；先取得该功能需要 Connect+ 的证据。

这两项延期不缩减本轮普通账号的其它已批准能力。桌面接入仍属于本轮；FTHR 空值恢复按下方用户决定列为已知问题。


## 已知问题 KI-001：FTHR 空值恢复（用户接受，2026-10-02）

FTHR 清空为 null 的契约尚未解决；数值 0 与 null 不等价。

用户明确要求将此项列为已知问题，不再测试或尝试恢复。本轮不以解决 KI-001 为验收条件；停止相关接口探测、哨兵值试写、清空和恢复测试。只有用户明确要求重开此问题后才继续。现有工具对 null 清空的拒绝保持不变，不声称该操作已支持。
