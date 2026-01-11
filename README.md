# Claude Code Configuration

My personal Claude Code MCP servers and skills configuration.

## MCP Servers (7 total)

| MCP Name | Type | Description |
|----------|------|-------------|
| gemini-cli | Node.js | Google Gemini CLI MCP server |
| codex | Node.js | OpenAI Codex MCP server |
| zotero | Python exe | Zotero reference manager (read-only) |
| zotero-writer | Python | Zotero writer (import papers via DOI) |
| github | Docker | GitHub API integration |
| playwright | Docker | Browser automation |
| wolfram-alpha | Docker | Computational intelligence |

## Skills (144 total)

Scientific skills from [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills).

### Categories

- **Databases**: PubMed, ChEMBL, UniProt, PDB, KEGG, etc.
- **Analysis**: scanpy, scikit-learn, statsmodels, PyTorch Lightning, etc.
- **Visualization**: matplotlib, plotly, seaborn, etc.
- **Writing**: scientific-writing, literature-review, peer-review, etc.
- **Chemistry**: rdkit, datamol, deepchem, etc.
- **Bioinformatics**: biopython, bioservices, scanpy, etc.

## Configuration Files

| File | Description |
|------|-------------|
| `mcp-servers.json` | MCP server configurations (template) |
| `zotero_writer.py` | Custom Zotero writer MCP source code |
| `skills-list.txt` | List of all installed skills |

## Installation

### MCP Servers

```bash
# Add MCP server (user-level)
claude mcp add <name> -s user -- <command> [args...]

# Add with environment variables
claude mcp add <name> -s user -e KEY=value -- <command> [args...]

# List all MCP servers
claude mcp list
```

### Skills

Copy skill folders to `~/.claude/skills/` directory.

```bash
# Clone scientific skills
git clone https://github.com/K-Dense-AI/claude-scientific-skills.git

# Copy to user skills directory (PowerShell)
Copy-Item -Path "claude-scientific-skills/scientific-skills/*" -Destination "$env:USERPROFILE/.claude/skills/" -Recurse -Force
```

## Configuration Paths

| Type | Path (Windows) |
|------|----------------|
| User MCP config | `%USERPROFILE%\.claude.json` (mcpServers field) |
| User settings | `%USERPROFILE%\.claude\settings.json` |
| User skills | `%USERPROFILE%\.claude\skills\` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` |
