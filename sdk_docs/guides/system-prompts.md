<!-- Source: https://platform.claude.com/docs/en/agent-sdk/modifying-system-prompts | Last updated: 2025-01-24 -->

# Modifying system prompts

Learn how to customize Claude's behavior by modifying system prompts

---

System prompts define Claude's behavior, capabilities, and response style. The Claude Agent SDK provides multiple ways to customize system prompts.

## Understanding system prompts

**Default behavior:** The Agent SDK uses a **minimal system prompt** by default. It contains only essential tool instructions but omits Claude Code's coding guidelines, response style, and project context. To include the full Claude Code system prompt, specify `systemPrompt: { preset: "claude_code" }` in TypeScript or `system_prompt={"type": "preset", "preset": "claude_code"}` in Python.

## Methods of modification

### Method 1: CLAUDE.md files (project-level instructions)

CLAUDE.md files provide project-specific context and instructions that are automatically read by the Agent SDK.

**Locations:**
- **Project-level:** `CLAUDE.md` or `.claude/CLAUDE.md` in your working directory
- **User-level:** `~/.claude/CLAUDE.md` for global instructions

**IMPORTANT:** The SDK only reads CLAUDE.md files when you explicitly configure `settingSources` (TypeScript) or `setting_sources` (Python):
- Include `'project'` to load project-level CLAUDE.md
- Include `'user'` to load user-level CLAUDE.md

```typescript TypeScript
for await (const message of query({
  prompt: "Add a new React component for user profiles",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
    },
    settingSources: ["project"], // Required to load CLAUDE.md from project
  },
})) {
  messages.push(message);
}
```

```python Python
async for message in query(
    prompt="Add a new React component for user profiles",
    options=ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code"
        },
        setting_sources=["project"]  # Required to load CLAUDE.md from project
    )
):
    messages.append(message)
```

### Method 2: Output styles (persistent configurations)

Output styles are saved configurations stored as markdown files in `~/.claude/output-styles` (user-level) or `.claude/output-styles` (project-level).

**Note:** Output styles are loaded when you include `settingSources: ['user']` or `settingSources: ['project']`.

### Method 3: Using `systemPrompt` with append

Add custom instructions while preserving all built-in functionality:

```typescript TypeScript
for await (const message of query({
  prompt: "Help me write a Python function to calculate fibonacci numbers",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
      append: "Always include detailed docstrings and type hints in Python code.",
    },
  },
})) {
  messages.push(message);
}
```

```python Python
async for message in query(
    prompt="Help me write a Python function to calculate fibonacci numbers",
    options=ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": "Always include detailed docstrings and type hints in Python code."
        }
    )
):
    messages.append(message)
```

### Method 4: Custom system prompts

Provide a custom string as `systemPrompt` to replace the default entirely:

```typescript TypeScript
const customPrompt = `You are a Python coding specialist.
Follow these guidelines:
- Write clean, well-documented code
- Use type hints for all functions
- Include comprehensive docstrings`;

for await (const message of query({
  prompt: "Create a data processing pipeline",
  options: {
    systemPrompt: customPrompt,
  },
})) {
  messages.push(message);
}
```

## Comparison of approaches

| Feature                 | CLAUDE.md           | Output Styles      | `systemPrompt` with append | Custom `systemPrompt`     |
| ----------------------- | ------------------- | ------------------ | -------------------------- | ------------------------- |
| **Persistence**         | Per-project file    | Saved as files     | Session only               | Session only              |
| **Reusability**         | Per-project         | Across projects    | Code duplication           | Code duplication          |
| **Default tools**       | Preserved           | Preserved          | Preserved                  | Lost (unless included)    |
| **Built-in safety**     | Maintained          | Maintained         | Maintained                 | Must be added             |
| **Version control**     | With project        | Yes                | With code                  | With code                 |

## When to use each approach

### CLAUDE.md
- Project-specific coding standards and conventions
- Documenting project structure and architecture
- Common commands (build, test, deploy)
- Team-shared context that should be version controlled

### Output styles
- Persistent behavior changes across sessions
- Team-shared configurations
- Specialized assistants (code reviewer, data scientist, DevOps)

### `systemPrompt` with append
- Adding specific coding standards or preferences
- Customizing output formatting
- Adding domain-specific knowledge
- Enhancing Claude Code's default behavior without losing tool instructions

### Custom `systemPrompt`
- Complete control over Claude's behavior
- Specialized single-session tasks
- Testing new prompt strategies
- Building specialized agents with unique behavior

## See also

- [Output styles](https://code.claude.com/docs/en/output-styles)
- [TypeScript SDK guide](/docs/en/agent-sdk/typescript)
- [Configuration guide](https://code.claude.com/docs/en/settings)
