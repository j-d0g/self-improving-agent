# Claude Agent SDK Documentation

> Local cache of Agent SDK documentation for agent context loading.
> Source: https://platform.claude.com/docs/en/agent-sdk

## Quick Reference

| Need to... | Read |
|------------|------|
| Get started | [quickstart.md](quickstart.md) |
| Python API reference | [python.md](python.md) |
| Control tool permissions | [guides/permissions.md](guides/permissions.md) |
| Add custom tools | [guides/custom-tools.md](guides/custom-tools.md) |
| Deploy to production | [guides/hosting.md](guides/hosting.md) |

---

## Core Reference

### [quickstart.md](quickstart.md)
**First-time setup and hello world example.**

- Installing Claude Code CLI and SDK
- Creating your first agent
- Running agents with `query()` and async iteration
- Permission modes: `acceptEdits`, `bypassPermissions`, `default`
- Tool presets: Read, Edit, Glob, Bash, WebSearch

### [python.md](python.md)
**Complete Python SDK API reference.**

- **`query()`** - One-shot queries (new session each call)
- **`ClaudeSDKClient`** - Stateful client for multi-turn conversations, interrupts, hooks, custom tools
- **`@tool` decorator** - Define custom MCP tools
- **`create_sdk_mcp_server()`** - Create in-process MCP servers
- **`ClaudeAgentOptions`** - All configuration options
- **Message types** - `AssistantMessage`, `ResultMessage`, `StreamEvent`, etc.
- **Hook types** - `HookMatcher`, `HookCallback`, input/output schemas
- **Tool I/O schemas** - Input/output for all built-in tools (Bash, Edit, Grep, etc.)
- **Sandbox configuration** - `SandboxSettings`, network restrictions

---

## Guides

### Input & Output

#### [guides/streaming-input.md](guides/streaming-input.md)
**Two modes for sending input to Claude.**

- **Streaming mode** - Async generator yielding message chunks
- **Single message mode** - Pass complete prompt string
- When to use each mode
- TypeScript and Python examples

#### [guides/structured-outputs.md](guides/structured-outputs.md)
**Get typed responses from Claude.**

- JSON Schema validation via `outputFormat`
- Pydantic models (Python) for type-safe output
- Zod schemas (TypeScript)
- Error handling for validation failures

---

### Permissions & Approvals

#### [guides/permissions.md](guides/permissions.md)
**Control what tools Claude can use and when.**

- Permission modes: `default`, `acceptEdits`, `bypassPermissions`, `plan`
- `allowedTools` and `disallowedTools` lists
- Wildcard patterns: `Bash(git *)`, `mcp__*`
- Permission rules and precedence

#### [guides/user-approvals-input.md](guides/user-approvals-input.md)
**Handle tool approval callbacks and clarifying questions.**

- `canUseTool` callback for custom approval logic
- `PermissionResultAllow` / `PermissionResultDeny` responses
- Modifying tool inputs before execution
- `AskUserQuestion` tool for gathering user input
- 60-second timeout handling

---

### Session Management

#### [guides/session-management.md](guides/session-management.md)
**Manage conversation state across queries.**

- Session IDs and the `resume` option
- Continuing vs. forking sessions (`fork_session`)
- Multi-turn conversations with `ClaudeSDKClient`
- Extracting session ID from messages

#### [guides/file-checkpointing.md](guides/file-checkpointing.md)
**Rewind file changes to previous states.**

- `enable_file_checkpointing=True` option
- `rewind_files(user_message_uuid)` method
- Checkpoint UUIDs from message metadata
- Use cases: undo bad edits, A/B testing approaches

---

### Hooks & Events

#### [guides/hooks.md](guides/hooks.md)
**Run custom code at key execution points.**

- **Hook events**: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`
- `HookMatcher` for filtering by tool name patterns
- Blocking tool execution with `decision: "block"`
- Modifying tool inputs/outputs
- Timeout configuration
- Python: `SessionStart`, `SessionEnd`, `Notification` not supported

---

### System Configuration

#### [guides/system-prompts.md](guides/system-prompts.md)
**Customize Claude's behavior and persona.**

- Custom system prompt string
- `preset: "claude_code"` with optional `append`
- Loading CLAUDE.md files via `setting_sources: ["project"]`
- Output style configuration

---

### Custom Tools & Extensions

#### [guides/custom-tools.md](guides/custom-tools.md)
**Add your own tools Claude can invoke.**

- `@tool` decorator with input schemas
- `create_sdk_mcp_server()` for in-process tools
- Tool naming: `mcp__<server>__<tool>`
- Returning text, images, errors
- Requires streaming input mode

#### [guides/mcp.md](guides/mcp.md)
**Connect external tools via Model Context Protocol.**

- Server types: stdio, HTTP, SSE, SDK
- `mcp_servers` configuration
- Tool discovery and `allowedTools` wildcards
- Authentication headers
- Tool search across MCP servers

#### [guides/plugins.md](guides/plugins.md)
**Load packaged extensions with commands, agents, and skills.**

- Plugin structure: `.claude-plugin/plugin.json`
- Loading via `plugins: [{"type": "local", "path": "./my-plugin"}]`
- Plugin namespacing: `plugin-name:command-name`
- Includes commands, agents, skills, hooks, MCP servers

---

### Agents & Skills

#### [guides/subagents.md](guides/subagents.md)
**Spawn specialized agents for focused subtasks.**

- `AgentDefinition` with description, prompt, tools, model
- Programmatic agents via `agents` option
- Filesystem agents in `.claude/agents/`
- Built-in `general-purpose` subagent
- Resuming subagents with `resume` parameter
- Tool restrictions per agent

#### [guides/skills.md](guides/skills.md)
**Model-invoked capabilities from SKILL.md files.**

- Location: `.claude/skills/` (project) or `~/.claude/skills/` (user)
- `setting_sources: ["user", "project"]` required to load
- `allowed_tools: ["Skill"]` to enable
- Automatic discovery based on description matching

#### [guides/slash-commands.md](guides/slash-commands.md)
**Built-in and custom slash commands.**

- Built-in: `/compact`, `/clear`, `/help`
- Custom commands in `.claude/commands/*.md`
- Frontmatter: `allowed-tools`, `description`, `argument-hint`
- File references (`@file.txt`) and shell execution (`!command`)

---

### Deployment & Operations

#### [guides/hosting.md](guides/hosting.md)
**Container and cloud deployment patterns.**

- Container patterns: ephemeral, long-running, hybrid, single-tenant
- Docker configuration examples
- Session management in containers
- Scaling considerations

#### [guides/secure-deployment.md](guides/secure-deployment.md)
**Security hardening for production.**

- Sandbox runtime isolation (gVisor, seccomp)
- Docker hardening: read-only rootfs, dropped capabilities
- Credential proxy pattern (avoid embedding secrets)
- Network restrictions and egress filtering
- Filesystem isolation

#### [guides/cost-tracking.md](guides/cost-tracking.md)
**Monitor token usage and costs.**

- `usage` field on assistant messages
- Deduplication via message IDs (same ID = same usage)
- `ResultMessage.total_cost_usd` for cumulative cost
- `modelUsage` breakdown by model
- Billing implementation patterns

---

## File Inventory

```
sdk_docs/
├── README.md              # This index
├── quickstart.md          # First-time setup
├── python.md              # Complete Python API reference
└── guides/
    ├── streaming-input.md     # Streaming vs single-turn
    ├── structured-outputs.md  # JSON Schema, Pydantic, Zod
    ├── permissions.md         # Permission modes and rules
    ├── user-approvals-input.md # canUseTool, AskUserQuestion
    ├── session-management.md  # Sessions, resume, fork
    ├── file-checkpointing.md  # Rewind file changes
    ├── hooks.md               # Pre/PostToolUse, etc.
    ├── system-prompts.md      # CLAUDE.md, custom prompts
    ├── custom-tools.md        # @tool, create_sdk_mcp_server
    ├── mcp.md                 # MCP server configuration
    ├── plugins.md             # Plugin loading
    ├── subagents.md           # AgentDefinition, Task tool
    ├── skills.md              # SKILL.md files
    ├── slash-commands.md      # /compact, custom commands
    ├── hosting.md             # Container deployment
    ├── secure-deployment.md   # Security hardening
    └── cost-tracking.md       # Token usage, billing
```
