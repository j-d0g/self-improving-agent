<!-- Source: https://platform.claude.com/docs/en/agent-sdk/slash-commands | Last updated: 2025-01-24 -->

# Slash Commands in the SDK

Learn how to use slash commands to control Claude Code sessions through the SDK

---

Slash commands provide a way to control Claude Code sessions with special commands that start with `/`. These commands can be sent through the SDK to perform actions like clearing conversation history, compacting messages, or getting help.

## Discovering Available Slash Commands

Access available slash commands from the system initialization message:

```typescript TypeScript
for await (const message of query({
  prompt: "Hello Claude",
  options: { maxTurns: 1 }
})) {
  if (message.type === "system" && message.subtype === "init") {
    console.log("Available slash commands:", message.slash_commands);
    // Example output: ["/compact", "/clear", "/help"]
  }
}
```

```python Python
async for message in query(
    prompt="Hello Claude",
    options={"max_turns": 1}
):
    if message.type == "system" and message.subtype == "init":
        print("Available slash commands:", message.slash_commands)
```

## Sending Slash Commands

Send slash commands by including them in your prompt string:

```typescript TypeScript
for await (const message of query({
  prompt: "/compact",
  options: { maxTurns: 1 }
})) {
  if (message.type === "result") {
    console.log("Command executed:", message.result);
  }
}
```

## Common Slash Commands

### `/compact` - Compact Conversation History

Reduces the size of your conversation history by summarizing older messages:

```typescript TypeScript
for await (const message of query({
  prompt: "/compact",
  options: { maxTurns: 1 }
})) {
  if (message.type === "system" && message.subtype === "compact_boundary") {
    console.log("Compaction completed");
    console.log("Pre-compaction tokens:", message.compact_metadata.pre_tokens);
  }
}
```

### `/clear` - Clear Conversation

Starts a fresh conversation by clearing all previous history:

```typescript TypeScript
for await (const message of query({
  prompt: "/clear",
  options: { maxTurns: 1 }
})) {
  if (message.type === "system" && message.subtype === "init") {
    console.log("Conversation cleared, new session started");
    console.log("Session ID:", message.session_id);
  }
}
```

## Creating Custom Slash Commands

Custom commands are defined as markdown files in specific directories:

- **Project commands**: `.claude/commands/` - Available only in the current project
- **Personal commands**: `~/.claude/commands/` - Available across all your projects

### File Format

Each custom command is a markdown file where the filename becomes the command name:

**Basic Example** - `.claude/commands/refactor.md`:

```markdown
Refactor the selected code to improve readability and maintainability.
Focus on clean code principles and best practices.
```

**With Frontmatter** - `.claude/commands/security-check.md`:

```markdown
---
allowed-tools: Read, Grep, Glob
description: Run security vulnerability scan
model: claude-sonnet-4-5-20250929
---

Analyze the codebase for security vulnerabilities including:
- SQL injection risks
- XSS vulnerabilities
- Exposed credentials
- Insecure configurations
```

### Using Custom Commands

```typescript TypeScript
// Custom commands appear in the slash_commands list
for await (const message of query({
  prompt: "Hello",
  options: { maxTurns: 1 }
})) {
  if (message.type === "system" && message.subtype === "init") {
    // Will include both built-in and custom commands
    console.log("Available commands:", message.slash_commands);
    // Example: ["/compact", "/clear", "/help", "/refactor", "/security-check"]
  }
}

// Use the custom command
for await (const message of query({
  prompt: "/refactor src/auth/login.ts",
  options: { maxTurns: 3 }
})) {
  if (message.type === "assistant") {
    console.log(message.content);
  }
}
```

### Advanced Features

#### Arguments and Placeholders

`.claude/commands/fix-issue.md`:

```markdown
---
argument-hint: [issue-number] [priority]
description: Fix a GitHub issue
---

Fix issue #$1 with priority $2.
Check the issue description and implement the necessary changes.
```

Usage: `/fix-issue 123 high`

#### Bash Command Execution

```markdown
---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*)
description: Create a git commit
---

## Context

- Current status: !`git status`
- Current diff: !`git diff HEAD`

## Task

Create a git commit with appropriate message based on the changes.
```

#### File References

```markdown
---
description: Review configuration files
---

Review the following configuration files for issues:
- Package config: @package.json
- TypeScript config: @tsconfig.json
- Environment config: @.env
```

## See Also

- [Slash Commands](https://code.claude.com/docs/en/slash-commands) - Complete slash command documentation
- [Subagents in the SDK](/docs/en/agent-sdk/subagents) - Similar filesystem-based configuration for subagents
