# Garminops 开发运行环境

Garminops 是 Transbridge marketplace 下的桌面本地开发插件。151 项注册操作通过六个 MCP 入口访问；完整支持程度见 [验证范围](../validation/LIVE_VERIFICATION.md) 与 [能力清单](../scope/CAPABILITY_INVENTORY.md)。历史版本、安装诊断和真实账号流水保存在忽略的本地 `logs/operations/`，不随插件分发。

## 安装开发依赖

首次克隆、生成包、注册 marketplace 与安装插件的顺序见根目录 README.md 中的“首次本地安装”。生成包不在 Git 中，必须先打包再安装。

需要 Python 3.12 或更高版本及 `uv`。Intel macOS 的锁定 `cryptography 50.0.2` 没有对应 wheel，需 Rust ≥1.83、Xcode 命令行工具与 OpenSSL 3 进行源码构建；必要时按 [上游安装说明](https://cryptography.io/en/latest/installation/) 设置 `OPENSSL_DIR`。在项目根目录执行：

```sh
uv sync --project garminops --extra test --locked
```

## 本地登录与区域

在自己的交互式终端运行；密码和验证码不要发到聊天：

```sh
garminops/.venv/bin/garminops login --region com
```

刷新凭证位于 `~/.config/transbridge/garmin/com/`，目录权限 700、CLI 创建的凭证文件权限 600。登录先通过临时会话认证并验证新客户端恢复，再保存区域会话。失败不替换已有连接；运行时不读取项目 `.env`。`cn` 使用独立区域目录。一次连接一个区域，不跨区同步；成功登录选择默认区域，显式 `serve --region` 可固定进程区域。

## 检查与运行

```sh
garminops/.venv/bin/garminops status --region com
garminops/.venv/bin/garminops serve --region com
```

`serve` 是 MCP stdio 服务，不接收普通聊天文字。插件 `mcp.json` 使用 `uv run --locked --project ${PLUGIN_ROOT} garminops serve`；安装包采用独立目录。重新生成包不等于已刷新安装副本或正在运行的会话。

真实读取可使用 `probe`，但必须来自已授权任务；单页结果不证明完整覆盖。个人响应、凭证、验证日志不得提交到项目或发布包。

## 写入边界与失败恢复

先用账号身份返回的 `account_id` 作为写操作的 `expected_account`；不使用浏览器配置名推断身份。历史记录不可修改，设备动作不随排课获得授权。

只有 `verified=true` 才表示回读确认。请求发送后失败，检查 `completed_requests` 和 `last_request` 并读取目标状态，不能盲目重复创建或改期。设置更新必须保留无关字段；骑行 FTP 的已观察关联设置效应应明确告知并检查。未验证的字段和资源状态不能推断为支持。

KI-001 的 null 清空契约未解决，0 不等于未设置；继续停止相关探测、清空和恢复测试，只有用户明确重开才继续。国区业务验证与 Connect+ 功能延期；这些状态不扩大其它操作的授权。

## 离线测试与真实验证

```sh
garminops/.venv/bin/pytest garminops/tests -q -rs
```

离线测试不应访问真实 Garmin 会话或发送业务请求。KI-001 相关测试明确 skip，不记为通过。`scripts/verify_garmin_*.py` 是真实验证入口，不能随离线测试自动执行；运行前需明确账号、区域、来源资源、未来日期与用户授权。失败后只清理本轮实际返回的资源 ID；超时且未返回 ID 时需核对服务状态，不能假设请求未生效。

## 本地打包

```sh
python3 scripts/package_garmin.py
```

生成 `dist/garminops/` 与 `dist/garminops-dev.zip`；本地 marketplace 指向前者。包使用显式文件清单，禁止 `logs/`、凭证和私有响应，不包含虚拟环境。原始日志即使留在本机，也不能成为清单输入。开发标记必须保留；安装与当前聊天工具加载分别验证。
