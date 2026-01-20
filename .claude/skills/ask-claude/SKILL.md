---
name: ask-claude
description: Answer questions about Claude Code features, settings, hooks, skills, MCP servers, and best practices.
---

# Ask Claude

Get answers about how to use Claude Code effectively.

## Usage

```
/ask-claude <question>
```

## Examples

```
/ask-claude where do I put project-specific rules?
/ask-claude how do hooks work?
/ask-claude what's the difference between skills and agents?
/ask-claude how do I create an MCP server?
```

## Behavior

When invoked, spawn a `claude-code-guide` agent to research the answer:

```
Task(
  subagent_type="claude-code-guide",
  prompt="<user's question>",
  description="Claude Code: <short summary>"
)
```

The agent has access to Claude Code documentation and can search the web for current information.

## Topics Covered

- Claude Code CLI features and commands
- Hooks (Stop, PreToolUse, PostToolUse, etc.)
- Skills and how to create them
- MCP servers and integrations
- Settings and configuration
- IDE integrations (VS Code, JetBrains)
- Keyboard shortcuts
- Best practices and workflows
