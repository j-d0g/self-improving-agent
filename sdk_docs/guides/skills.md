<!-- Source: https://platform.claude.com/docs/en/agent-sdk/skills | Last updated: 2025-01-24 -->

# Agent Skills in the SDK

Extend Claude with specialized capabilities using Agent Skills in the Claude Agent SDK

---

## Overview

Agent Skills extend Claude with specialized capabilities that Claude autonomously invokes when relevant. Skills are packaged as `SKILL.md` files containing instructions, descriptions, and optional supporting resources.

## How Skills Work with the SDK

When using the Claude Agent SDK, Skills are:

1. **Defined as filesystem artifacts**: Created as `SKILL.md` files in specific directories (`.claude/skills/`)
2. **Loaded from filesystem**: Skills are loaded from configured filesystem locations. You must specify `settingSources` (TypeScript) or `setting_sources` (Python) to load Skills from the filesystem
3. **Automatically discovered**: Once filesystem settings are loaded, Skill metadata is discovered at startup
4. **Model-invoked**: Claude autonomously chooses when to use them based on context
5. **Enabled via allowed_tools**: Add `"Skill"` to your `allowed_tools` to enable Skills

**Note:** By default, the SDK does not load any filesystem settings. To use Skills, you must explicitly configure `settingSources: ['user', 'project']` (TypeScript) or `setting_sources=["user", "project"]` (Python).

## Using Skills with the SDK

```python Python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    cwd="/path/to/project",  # Project with .claude/skills/
    setting_sources=["user", "project"],  # Load Skills from filesystem
    allowed_tools=["Skill", "Read", "Write", "Bash"]  # Enable Skill tool
)

async for message in query(
    prompt="Help me process this PDF document",
    options=options
):
    print(message)
```

```typescript TypeScript
for await (const message of query({
  prompt: "Help me process this PDF document",
  options: {
    cwd: "/path/to/project",  // Project with .claude/skills/
    settingSources: ["user", "project"],  // Load Skills from filesystem
    allowedTools: ["Skill", "Read", "Write", "Bash"]  // Enable Skill tool
  }
})) {
  console.log(message);
}
```

## Skill Locations

- **Project Skills** (`.claude/skills/`): Shared with your team via git
- **User Skills** (`~/.claude/skills/`): Personal Skills across all projects
- **Plugin Skills**: Bundled with installed Claude Code plugins

## Creating Skills

Skills are defined as directories containing a `SKILL.md` file with YAML frontmatter and Markdown content:

```bash
.claude/skills/processing-pdfs/
└── SKILL.md
```

The `description` field determines when Claude invokes your Skill.

## Tool Restrictions

**Note:** The `allowed-tools` frontmatter field in SKILL.md is only supported when using Claude Code CLI directly. **It does not apply when using Skills through the SDK**.

Control tool access through the main `allowedTools` option:

```python Python
options = ClaudeAgentOptions(
    setting_sources=["user", "project"],
    allowed_tools=["Skill", "Read", "Grep", "Glob"]  # Restricted toolset
)
```

## Discovering Available Skills

```python Python
options = ClaudeAgentOptions(
    setting_sources=["user", "project"],
    allowed_tools=["Skill"]
)

async for message in query(
    prompt="What Skills are available?",
    options=options
):
    print(message)
```

## Testing Skills

Test Skills by asking questions that match their descriptions:

```python Python
options = ClaudeAgentOptions(
    cwd="/path/to/project",
    setting_sources=["user", "project"],
    allowed_tools=["Skill", "Read", "Bash"]
)

async for message in query(
    prompt="Extract text from invoice.pdf",
    options=options
):
    print(message)
```

## Troubleshooting

### Skills Not Found

**Check settingSources configuration**: Skills are only loaded when you explicitly configure `settingSources`/`setting_sources`:

```python Python
# Wrong - Skills won't be loaded
options = ClaudeAgentOptions(
    allowed_tools=["Skill"]
)

# Correct - Skills will be loaded
options = ClaudeAgentOptions(
    setting_sources=["user", "project"],  # Required to load Skills
    allowed_tools=["Skill"]
)
```

**Check working directory**: The SDK loads Skills relative to the `cwd` option. Ensure it points to a directory containing `.claude/skills/`.

**Verify filesystem location**:
```bash
ls .claude/skills/*/SKILL.md
ls ~/.claude/skills/*/SKILL.md
```

### Skill Not Being Used

- Confirm `"Skill"` is in your `allowedTools`
- Check the description is specific and includes relevant keywords

## Related Documentation

- [Agent Skills in Claude Code](https://code.claude.com/docs/en/skills)
- [Agent Skills Best Practices](/docs/en/agents-and-tools/agent-skills/best-practices)
- [Subagents in the SDK](/docs/en/agent-sdk/subagents)
