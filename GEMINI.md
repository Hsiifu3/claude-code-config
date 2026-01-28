# gemini-mcp-tool

## Project Overview

`gemini-mcp-tool` is a Model Context Protocol (MCP) server that integrates the [Google Gemini CLI](https://github.com/google-gemini/gemini-cli) with MCP-compliant AI assistants (like Claude).

**Key Capabilities:**
*   **Large Context Analysis:** Allows AI assistants to analyze large files or entire directories using Gemini's massive context window via the `@` syntax.
*   **Web Search:** Enables natural language web searches powered by Gemini.
*   **Safe Code Execution:** Provides a sandbox environment (`-s` mode) to safely write and test code.
*   **Tool Suite:** Includes tools for asking Gemini questions, brainstorming, and fetching content chunks.

**Architecture:**
*   **Framework:** Built with Node.js and TypeScript using the `@modelcontextprotocol/sdk`.
*   **Entry Point:** `src/index.ts` initializes the MCP server, handles request/response cycles (tools, prompts), and manages progress notifications.
*   **Tool Registry:** Tools are defined in `src/tools/` and registered in `src/tools/index.ts`.
*   **Execution:** Relies on `src/utils/geminiExecutor.ts` and `src/utils/commandExecutor.ts` to interface with the underlying Gemini CLI.

## Building and Running

### Prerequisites
*   Node.js >= 16.0.0
*   Google Gemini CLI installed and configured.

### Commands
*   **Build:** `npm run build` (Compiles TypeScript to `dist/`)
*   **Start:** `npm start` (Runs the compiled server from `dist/index.js`)
*   **Development:** `npm run dev` (Compiles and runs immediately)
*   **Lint:** `npm run lint` (Runs TypeScript type checking)
*   **Documentation:**
    *   `npm run docs:dev` (Start VitePress dev server)
    *   `npm run docs:build` (Build documentation site)

## Development Conventions

*   **Language:** TypeScript.
*   **Structure:**
    *   `src/`: Source code.
    *   `src/tools/`: Individual tool implementations (e.g., `ask-gemini.tool.ts`).
    *   `dist/`: Compiled JavaScript output (do not edit manually).
    *   `docs/`: VitePress documentation source.
*   **Style:** Follows standard TypeScript/Node.js patterns.
*   **Testing:** Currently minimal (`npm test` exits with 0).
*   **Validation:** Uses `zod` for schema validation.
*   **Output:** Uses `chalk` for terminal styling.

## Key Files

*   `package.json`: Project metadata, dependencies, and scripts.
*   `src/index.ts`: Main MCP server entry point.
*   `src/tools/index.ts`: Central registry for exporting available tools.
*   `src/tools/registry.ts`: Logic for registering and retrieving tools.
*   `README.md`: User-facing documentation and usage examples.
