---
name: add-agent
description: Create and register a new sub-agent that can be spawned via the Task tool. This skill should be used when users want to add a custom agent with specific behaviors, tools, or expertise.
---

# Add Agent

Create and register custom sub-agents for use with the Task tool.

## Agent File Structure

Each agent is a markdown file with YAML frontmatter:

```markdown
---
name: agent-name
description: One-line description of what this agent does. Used by Claude to decide when to spawn it.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

[Agent instructions in markdown]
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier used with Task tool's `subagent_type` |
| `description` | Yes | When/why to use this agent (helps Claude decide) |
| `tools` | No | Comma-separated list of available tools |
| `model` | No | Default model: `sonnet`, `haiku`, or `opus` |

### Agent Instructions

The markdown body contains:
- Role definition and expertise
- Core behaviors and workflows
- Output format expectations
- Domain-specific knowledge

## Registration

Agents must be registered in a `plugin.json` to be available via Task tool.

### File Location

```
.claude/agents/
├── .claude-plugin/
│   └── plugin.json    ← Register agents here
├── my-agent.md
└── another-agent.md
```

### plugin.json Format

```json
{
  "name": "project-agents",
  "version": "1.0.0",
  "description": "Custom agents for this project",
  "agents": [
    "../my-agent.md",
    "../another-agent.md"
  ]
}
```

Paths are relative to the plugin.json location.

## Workflow

To add a new agent:

1. **Create the agent file** at `.claude/agents/<agent-name>.md`
2. **Add to plugin.json** in the `agents` array
3. **Restart Claude Code** for registration to take effect
4. **Test** by spawning via Task tool with `subagent_type: "<agent-name>"`

## Example

Creating a `code-explainer` agent:

1. Create `.claude/agents/code-explainer.md`:

```markdown
---
name: code-explainer
description: Explain code in plain language. Use when users ask "what does this code do?" or want code walkthroughs.
tools: Read, Glob, Grep
model: haiku
---

You explain code clearly and concisely.

## Approach

1. Read the code
2. Identify the main purpose
3. Explain in plain language, avoiding jargon
4. Highlight key patterns or potential issues
```

2. Update `.claude/agents/.claude-plugin/plugin.json`:

```json
{
  "agents": [
    "../code-explainer.md",
    "../existing-agent.md"
  ]
}
```

3. Restart Claude Code

4. Test by spawning the agent and verifying expected behavior appears in output
