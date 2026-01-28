# MCP Server 项目记忆

## 用户级 MCP 配置

**配置文件路径**: `C:\Users\90643\.claude.json`

在 `mcpServers` 字段中配置，当前已配置的用户级 MCP 服务器：

| MCP 名称 | 命令 | 说明 |
|---------|------|------|
| gemini-cli | `node C:/Users/90643/Desktop/Code/MCP_server/gemini-mcp-tool/dist/index.js` | Gemini CLI MCP 服务器 |
| codex | `node C:/Users/90643/AppData/Roaming/npm/node_modules/codex-mcp-server/dist/index.js` | OpenAI Codex MCP 服务器 |
| zotero | `C:/Anaconda/Scripts/zotero-mcp.exe serve` | Zotero 文献管理 MCP（只读） |
| zotero-writer | `python C:/Users/90643/Desktop/Code/MCP_server/zotero_writer.py` | Zotero 写入 MCP（通过 DOI 导入文献） |

## MCP 管理命令

```bash
# 列出所有 MCP 服务器
claude mcp list

# 查看特定 MCP 配置
claude mcp get <name>

# 添加用户级 MCP
claude mcp add <name> -s user -- <command> [args...]

# 添加带环境变量的 MCP
claude mcp add <name> -s user -e KEY=value -- <command> [args...]

# 删除用户级 MCP
claude mcp remove <name> -s user
```

## 项目结构

- `gemini-mcp-tool/` - Gemini CLI MCP 服务器源码
- `.claude/settings.local.json` - 项目级别权限配置

## 相关配置文件位置

| 配置类型 | 路径 |
|---------|------|
| 用户级 MCP 配置 | `C:\Users\90643\.claude.json` (mcpServers 字段) |
| 用户级 Claude 设置 | `C:\Users\90643\.claude\settings.json` |
| 项目级权限配置 | `.claude/settings.local.json` |
| Claude Desktop 配置 | `C:\Users\90643\AppData\Roaming\Claude\claude_desktop_config.json` |
| 用户级 Skills | `C:\Users\90643\.claude\skills\` |
