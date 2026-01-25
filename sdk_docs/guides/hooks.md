<!-- Source: https://platform.claude.com/docs/en/agent-sdk/hooks | Last updated: 2025-01-24 -->

# Intercept and control agent behavior with hooks

Intercept and customize agent behavior at key execution points with hooks

---

Hooks let you intercept agent execution at key points to add validation, logging, security controls, or custom logic. With hooks, you can:

- **Block dangerous operations** before they execute, like destructive shell commands or unauthorized file access
- **Log and audit** every tool call for compliance, debugging, or analytics
- **Transform inputs and outputs** to sanitize data, inject credentials, or redirect file paths
- **Require human approval** for sensitive actions like database writes or API calls
- **Track session lifecycle** to manage state, clean up resources, or send notifications

A hook has two parts:

1. **The callback function**: the logic that runs when the hook fires
2. **The hook configuration**: tells the SDK which event to hook into (like `PreToolUse`) and which tools to match

## Example: Block .env file modifications

```python Python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, HookMatcher

async def protect_env_files(input_data, tool_use_id, context):
    file_path = input_data['tool_input'].get('file_path', '')
    file_name = file_path.split('/')[-1]

    if file_name == '.env':
        return {
            'hookSpecificOutput': {
                'hookEventName': input_data['hook_event_name'],
                'permissionDecision': 'deny',
                'permissionDecisionReason': 'Cannot modify .env files'
            }
        }
    return {}

async def main():
    async for message in query(
        prompt="Update the database configuration",
        options=ClaudeAgentOptions(
            hooks={
                'PreToolUse': [HookMatcher(matcher='Write|Edit', hooks=[protect_env_files])]
            }
        )
    ):
        print(message)

asyncio.run(main())
```

```typescript TypeScript
import { query, HookCallback, PreToolUseHookInput } from "@anthropic-ai/claude-agent-sdk";

const protectEnvFiles: HookCallback = async (input, toolUseID, { signal }) => {
  const preInput = input as PreToolUseHookInput;
  const filePath = preInput.tool_input?.file_path as string;
  const fileName = filePath?.split('/').pop();

  if (fileName === '.env') {
    return {
      hookSpecificOutput: {
        hookEventName: input.hook_event_name,
        permissionDecision: 'deny',
        permissionDecisionReason: 'Cannot modify .env files'
      }
    };
  }
  return {};
};

for await (const message of query({
  prompt: "Update the database configuration",
  options: {
    hooks: {
      PreToolUse: [{ matcher: 'Write|Edit', hooks: [protectEnvFiles] }]
    }
  }
})) {
  console.log(message);
}
```

## Available hooks

| Hook Event | Python SDK | TypeScript SDK | What triggers it | Example use case |
|------------|------------|----------------|------------------|------------------|
| `PreToolUse` | Yes | Yes | Tool call request (can block or modify) | Block dangerous shell commands |
| `PostToolUse` | Yes | Yes | Tool execution result | Log all file changes to audit trail |
| `PostToolUseFailure` | No | Yes | Tool execution failure | Handle or log tool errors |
| `UserPromptSubmit` | Yes | Yes | User prompt submission | Inject additional context into prompts |
| `Stop` | Yes | Yes | Agent execution stop | Save session state before exit |
| `SubagentStart` | No | Yes | Subagent initialization | Track parallel task spawning |
| `SubagentStop` | Yes | Yes | Subagent completion | Aggregate results from parallel tasks |
| `PreCompact` | Yes | Yes | Conversation compaction request | Archive full transcript before summarizing |
| `PermissionRequest` | No | Yes | Permission dialog would be displayed | Custom permission handling |
| `SessionStart` | No | Yes | Session initialization | Initialize logging and telemetry |
| `SessionEnd` | No | Yes | Session termination | Clean up temporary resources |
| `Notification` | No | Yes | Agent status messages | Send agent status updates to Slack or PagerDuty |

## Configure hooks

```python Python
async for message in query(
    prompt="Your prompt",
    options=ClaudeAgentOptions(
        hooks={
            'PreToolUse': [HookMatcher(matcher='Bash', hooks=[my_callback])]
        }
    )
):
    print(message)
```

```typescript TypeScript
for await (const message of query({
  prompt: "Your prompt",
  options: {
    hooks: {
      PreToolUse: [{ matcher: 'Bash', hooks: [myCallback] }]
    }
  }
})) {
  console.log(message);
}
```

### Matchers

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `matcher` | `string` | `undefined` | Regex pattern to match tool names. Built-in tools include `Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`, `WebFetch`, `Task`, and others. MCP tools use the pattern `mcp__<server>__<action>`. |
| `hooks` | `HookCallback[]` | - | Required. Array of callback functions to execute when the pattern matches |
| `timeout` | `number` | `60` | Timeout in seconds; increase for hooks that make external API calls |

### Callback function inputs

Every hook callback receives three arguments:

1. **Input data** (`dict` / `HookInput`): Event details
2. **Tool use ID** (`str | None` / `string | null`): Correlate `PreToolUse` and `PostToolUse` events
3. **Context** (`HookContext`): In TypeScript, contains a `signal` property (`AbortSignal`) for cancellation

### Callback outputs

Return an empty object `{}` to allow the operation without changes. To block, modify, or add context:

**Top-level fields** (outside `hookSpecificOutput`):

| Field | Type | Description |
|-------|------|-------------|
| `continue` | `boolean` | Whether the agent should continue after this hook (default: `true`) |
| `stopReason` | `string` | Message shown when `continue` is `false` |
| `suppressOutput` | `boolean` | Hide stdout from the transcript (default: `false`) |
| `systemMessage` | `string` | Message injected into the conversation for Claude to see |

**Fields inside `hookSpecificOutput`**:

| Field | Type | Hooks | Description |
|-------|------|-------|-------------|
| `hookEventName` | `string` | All | Required. Use `input.hook_event_name` to match the current event |
| `permissionDecision` | `'allow'` \| `'deny'` \| `'ask'` | PreToolUse | Controls whether the tool executes |
| `permissionDecisionReason` | `string` | PreToolUse | Explanation shown to Claude for the decision |
| `updatedInput` | `object` | PreToolUse | Modified tool input (requires `permissionDecision: 'allow'`) |
| `additionalContext` | `string` | PreToolUse, PostToolUse, UserPromptSubmit, SessionStart, SubagentStart | Context added to the conversation |

## Common patterns

### Block a tool

```python Python
async def block_dangerous_commands(input_data, tool_use_id, context):
    if input_data['hook_event_name'] != 'PreToolUse':
        return {}

    command = input_data['tool_input'].get('command', '')

    if 'rm -rf /' in command:
        return {
            'hookSpecificOutput': {
                'hookEventName': input_data['hook_event_name'],
                'permissionDecision': 'deny',
                'permissionDecisionReason': 'Dangerous command blocked: rm -rf /'
            }
        }
    return {}
```

### Modify tool input

```python Python
async def redirect_to_sandbox(input_data, tool_use_id, context):
    if input_data['hook_event_name'] != 'PreToolUse':
        return {}

    if input_data['tool_name'] == 'Write':
        original_path = input_data['tool_input'].get('file_path', '')
        return {
            'hookSpecificOutput': {
                'hookEventName': input_data['hook_event_name'],
                'permissionDecision': 'allow',
                'updatedInput': {
                    **input_data['tool_input'],
                    'file_path': f'/sandbox{original_path}'
                }
            }
        }
    return {}
```

### Auto-approve specific tools

```python Python
async def auto_approve_read_only(input_data, tool_use_id, context):
    if input_data['hook_event_name'] != 'PreToolUse':
        return {}

    read_only_tools = ['Read', 'Glob', 'Grep', 'LS']
    if input_data['tool_name'] in read_only_tools:
        return {
            'hookSpecificOutput': {
                'hookEventName': input_data['hook_event_name'],
                'permissionDecision': 'allow',
                'permissionDecisionReason': 'Read-only tool auto-approved'
            }
        }
    return {}
```

### Chaining multiple hooks

```python Python
options = ClaudeAgentOptions(
    hooks={
        'PreToolUse': [
            HookMatcher(hooks=[rate_limiter]),        # First: check rate limits
            HookMatcher(hooks=[authorization_check]), # Second: verify permissions
            HookMatcher(hooks=[input_sanitizer]),     # Third: sanitize inputs
            HookMatcher(hooks=[audit_logger])         # Last: log the action
        ]
    }
)
```

## Permission decision flow

When multiple hooks or permission rules apply, the SDK evaluates them in this order:

1. **Deny** rules are checked first (any match = immediate denial)
2. **Ask** rules are checked second
3. **Allow** rules are checked third
4. **Default to Ask** if nothing matches

If any hook returns `deny`, the operation is blocked—other hooks returning `allow` won't override it.

## Learn more

- [Permissions](/docs/en/agent-sdk/permissions): control what your agent can do
- [Custom Tools](/docs/en/agent-sdk/custom-tools): build tools to extend agent capabilities
- [TypeScript SDK Reference](/docs/en/agent-sdk/typescript)
- [Python SDK Reference](/docs/en/agent-sdk/python)
