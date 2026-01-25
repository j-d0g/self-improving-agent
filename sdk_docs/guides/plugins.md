<!-- Source: https://platform.claude.com/docs/en/agent-sdk/plugins | Last updated: 2025-01-24 -->

# Plugins in the SDK

Load custom plugins to extend Claude Code with commands, agents, skills, and hooks through the Agent SDK

---

Plugins allow you to extend Claude Code with custom functionality that can be shared across projects. Through the Agent SDK, you can programmatically load plugins from local directories to add custom slash commands, agents, skills, hooks, and MCP servers to your agent sessions.

## What are plugins?

Plugins are packages of Claude Code extensions that can include:
- **Commands**: Custom slash commands
- **Agents**: Specialized subagents for specific tasks
- **Skills**: Model-invoked capabilities that Claude uses autonomously
- **Hooks**: Event handlers that respond to tool use and other events
- **MCP servers**: External tool integrations via Model Context Protocol

## Loading plugins

Load plugins by providing their local file system paths:

```typescript TypeScript
for await (const message of query({
  prompt: "Hello",
  options: {
    plugins: [
      { type: "local", path: "./my-plugin" },
      { type: "local", path: "/absolute/path/to/another-plugin" }
    ]
  }
})) {
  // Plugin commands, agents, and other features are now available
}
```

```python Python
async for message in query(
    prompt="Hello",
    options={
        "plugins": [
            {"type": "local", "path": "./my-plugin"},
            {"type": "local", "path": "/absolute/path/to/another-plugin"}
        ]
    }
):
    pass
```

**Note:** The path should point to the plugin's root directory (the directory containing `.claude-plugin/plugin.json`).

## Verifying plugin installation

```typescript TypeScript
for await (const message of query({
  prompt: "Hello",
  options: {
    plugins: [{ type: "local", path: "./my-plugin" }]
  }
})) {
  if (message.type === "system" && message.subtype === "init") {
    console.log("Plugins:", message.plugins);
    console.log("Commands:", message.slash_commands);
  }
}
```

## Using plugin commands

Commands from plugins are namespaced with the plugin name: `plugin-name:command-name`.

```typescript TypeScript
for await (const message of query({
  prompt: "/my-plugin:greet",  // Use plugin command with namespace
  options: {
    plugins: [{ type: "local", path: "./my-plugin" }]
  }
})) {
  if (message.type === "assistant") {
    console.log(message.content);
  }
}
```

## Plugin structure reference

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # Required: plugin manifest
├── commands/                 # Custom slash commands
│   └── custom-cmd.md
├── agents/                   # Custom agents
│   └── specialist.md
├── skills/                   # Agent Skills
│   └── my-skill/
│       └── SKILL.md
├── hooks/                    # Event handlers
│   └── hooks.json
└── .mcp.json                # MCP server definitions
```

## Common use cases

### Development and testing

```typescript
plugins: [
  { type: "local", path: "./dev-plugins/my-plugin" }
]
```

### Project-specific extensions

```typescript
plugins: [
  { type: "local", path: "./project-plugins/team-workflows" }
]
```

### Multiple plugin sources

```typescript
plugins: [
  { type: "local", path: "./local-plugin" },
  { type: "local", path: "~/.claude/custom-plugins/shared-plugin" }
]
```

## Troubleshooting

### Plugin not loading
1. Check the path points to the plugin root directory (containing `.claude-plugin/`)
2. Validate plugin.json has valid JSON syntax
3. Check file permissions

### Commands not available
1. Use the namespace: `plugin-name:command-name`
2. Verify the command appears in `slash_commands` with the correct namespace
3. Validate command markdown files are in the `commands/` directory

### Path resolution issues
1. Relative paths are resolved from your current working directory
2. Consider using absolute paths for reliability
3. Use path utilities to construct paths correctly

## See also

- [Plugins](https://code.claude.com/docs/en/plugins) - Complete plugin development guide
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference) - Technical specifications
- [Slash Commands](/docs/en/agent-sdk/slash-commands)
- [Subagents](/docs/en/agent-sdk/subagents)
- [Skills](/docs/en/agent-sdk/skills)
