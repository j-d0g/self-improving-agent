<!-- Source: https://platform.claude.com/docs/en/agent-sdk/permissions | Last updated: 2025-01-24 -->

# Configure permissions

Control how your agent uses tools with permission modes, hooks, and declarative allow/deny rules.

---

The Claude Agent SDK provides permission controls to manage how Claude uses tools. Use permission modes and rules to define what's allowed automatically, and the `canUseTool` callback to handle everything else at runtime.

## How permissions are evaluated

When Claude requests a tool, the SDK checks permissions in this order:

1. **Hooks**: Run hooks first, which can allow, deny, or continue to the next step
2. **Permission rules**: Check rules defined in settings.json: `deny` rules first, then `allow` rules, then `ask` rules
3. **Permission mode**: Apply the active permission mode (`bypassPermissions`, `acceptEdits`, `dontAsk`, etc.)
4. **canUseTool callback**: If not resolved by rules or modes, call your `canUseTool` callback for a decision

## Permission modes

### Available modes

| Mode | Description | Tool behavior |
| :--- | :---------- | :------------ |
| `default` | Standard permission behavior | No auto-approvals; unmatched tools trigger your `canUseTool` callback |
| `acceptEdits` | Auto-accept file edits | File edits and filesystem operations (`mkdir`, `rm`, `mv`, etc.) are automatically approved |
| `bypassPermissions` | Bypass all permission checks | All tools run without permission prompts (use with caution) |
| `plan` | Planning mode | No tool execution; Claude plans without making changes |

**Warning**: When using `bypassPermissions`, all subagents inherit this mode and it cannot be overridden.

### Set permission mode

**At query time:**

```python Python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Help me refactor this code",
    options=ClaudeAgentOptions(
        permission_mode="default",
    ),
):
    if hasattr(message, "result"):
        print(message.result)
```

```typescript TypeScript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Help me refactor this code",
  options: {
    permissionMode: "default",
  },
})) {
  if ("result" in message) {
    console.log(message.result);
  }
}
```

**During streaming:**

```python Python
q = query(
    prompt="Help me refactor this code",
    options=ClaudeAgentOptions(
        permission_mode="default",
    ),
)

# Change mode dynamically mid-session
await q.set_permission_mode("acceptEdits")

async for message in q:
    if hasattr(message, "result"):
        print(message.result)
```

```typescript TypeScript
const q = query({
  prompt: "Help me refactor this code",
  options: {
    permissionMode: "default",
  },
});

// Change mode dynamically mid-session
await q.setPermissionMode("acceptEdits");

for await (const message of q) {
  if ("result" in message) {
    console.log(message.result);
  }
}
```

### Mode details

#### Accept edits mode (`acceptEdits`)

Auto-approves file operations so Claude can edit code without prompting. Other tools (like Bash commands that aren't filesystem operations) still require normal permissions.

**Auto-approved operations:**
- File edits (Edit, Write tools)
- Filesystem commands: `mkdir`, `touch`, `rm`, `mv`, `cp`

**Use when:** you trust Claude's edits and want faster iteration.

#### Bypass permissions mode (`bypassPermissions`)

Auto-approves all tool uses without prompts. Hooks still execute and can block operations if needed.

**Use with extreme caution.** Claude has full system access in this mode.

#### Plan mode (`plan`)

Prevents tool execution entirely. Claude can analyze code and create plans but cannot make changes.

**Use when:** you want Claude to propose changes without executing them.

## Related resources

- [Handle approvals and user input](/docs/en/agent-sdk/user-input): interactive approval prompts and clarifying questions
- [Hooks guide](/docs/en/agent-sdk/hooks): run custom code at key points in the agent lifecycle
- [Permission rules](https://code.claude.com/docs/en/settings#permission-settings): declarative allow/deny rules in `settings.json`
