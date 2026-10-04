# Transbridge

Codex/ChatGPT 桌面本地插件 marketplace。

- Marketplace：`transbridge`
- Plugin：`garminops`，显示名称 Garminops
- 当前 skill：`garminops`，连接 Garmin Connect

项目文档统一从 [项目文档](docs/README.md) 进入，包含范围、研究、验证、运行与交接。

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
