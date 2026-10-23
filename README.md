# Transbridge

Codex/ChatGPT 桌面本地插件 marketplace。

- Marketplace：`transbridge`
- Plugin：`garminops`，显示名称 Garminops
- 当前 skill：`garminops`，连接 Garmin Connect

项目文档统一从 [项目文档](docs/README.md) 进入，包含范围、研究、验证、运行与交接。

## 首次本地安装

需要 Git、Python ≥3.12、`uv`，以及支持本地插件的 Codex CLI／ChatGPT 桌面宿主。下面的 `codex` 指宿主提供的 CLI；macOS 若命令不在 PATH，可使用 `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`。

Intel macOS 安装当前锁定的 `cryptography 50.0.2` 需要源码构建：先准备 Rust ≥1.83、Xcode 命令行工具和 OpenSSL 3；必要时按 [cryptography 官方安装说明](https://cryptography.io/en/latest/installation/) 设置 `OPENSSL_DIR`。锁文件没有该版本的 Intel macOS wheel，缺少工具链时不能把安装失败当作账号或 Garmin 服务错误。其它系统可能使用 wheel，其宿主兼容性仍需分别验证。

在终端克隆公开仓库并安装：

```sh
git clone https://github.com/n0rvyn/transbridge.git
cd transbridge
python3 scripts/package_garmin.py
codex plugin marketplace add .
codex plugin add garminops@transbridge
uv run --locked --project garminops garminops status --region com
```

必须先打包：marketplace 指向 `./dist/garminops`，生成目录不在 Git 中。插件启动也使用 `uv run --locked`，安装依赖可能需要网络；安装和启动都不等于 Garmin 已登录。

在自己的交互式终端登录，不把密码或验证码发给聊天：

```sh
uv run --locked --project garminops garminops login --region com
```

`com` 与 `cn` 使用各自的会话目录，选择与你获授权账号对应的区域。登录后开启新的宿主会话再选择 Garminops；现有聊天不会因为源码打包或安装自动获得新工具。操作前核对实际 Garmin 服务身份，登录不授予任意业务操作权限。

开发测试与能力限制见 [运行说明](docs/operations/RUNNING.md)；这仍是开发版本。


```text
transbridge/
├── .claude-plugin/marketplace.json
├── garminops/
│   ├── plugin.json
│   ├── mcp.json
│   ├── skills/garminops/
│   ├── src/
│   └── tests/
├── docs/                    # 项目文档
├── scripts/
└── dist/                    # 生成包，不在这里维护文档
```

打包：`python3 scripts/package_garmin.py`。开发规则见 [AGENTS.md](AGENTS.md)，恢复会话见 [CLAUDE.md](CLAUDE.md)。
