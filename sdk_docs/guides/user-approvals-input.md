<!-- Source: https://platform.claude.com/docs/en/agent-sdk/user-input | Last updated: 2025-01-24 -->

# Handle approvals and user input

Surface Claude's approval requests and clarifying questions to users, then return their decisions to the SDK.

---

While working on a task, Claude sometimes needs to check in with users. It might need permission before deleting files, or need to ask which database to use for a new project. Your application needs to surface these requests to users so Claude can continue with their input.

Claude requests user input in two situations:
1. When it needs **permission to use a tool** (like deleting files or running commands)
2. When it has **clarifying questions** (via the `AskUserQuestion` tool)

Both trigger your `canUseTool` callback, which pauses execution until you return a response.

## Detect when Claude needs input

Pass a `canUseTool` callback in your query options:

```python Python
async def handle_tool_request(tool_name, input_data, context):
    # Prompt user and return allow or deny
    ...

options = ClaudeAgentOptions(can_use_tool=handle_tool_request)
```

```typescript TypeScript
async function handleToolRequest(toolName, input) {
  // Prompt user and return allow or deny
}

const options = { canUseTool: handleToolRequest }
```

The callback fires in two cases:

1. **Tool needs approval**: Claude wants to use a tool that isn't auto-approved
2. **Claude asks a question**: Claude calls the `AskUserQuestion` tool

Your callback must return within **60 seconds** or Claude will assume the request was denied.

## Handle tool approval requests

Common tool input fields:

| Tool | Input fields |
|------|--------------|
| `Bash` | `command`, `description`, `timeout` |
| `Write` | `file_path`, `content` |
| `Edit` | `file_path`, `old_string`, `new_string` |
| `Read` | `file_path`, `offset`, `limit` |

### Respond to tool requests

| Response | Python | TypeScript |
|----------|--------|------------|
| **Allow** | `PermissionResultAllow(updated_input=...)` | `{ behavior: "allow", updatedInput }` |
| **Deny** | `PermissionResultDeny(message=...)` | `{ behavior: "deny", message }` |

```python Python
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

# Allow the tool to execute
return PermissionResultAllow(updated_input=input_data)

# Block the tool
return PermissionResultDeny(message="User rejected this action")
```

```typescript TypeScript
// Allow the tool to execute
return { behavior: "allow", updatedInput: input };

// Block the tool
return { behavior: "deny", message: "User rejected this action" };
```

### Response options

- **Approve**: let the tool execute as Claude requested
- **Approve with changes**: modify the input before execution
- **Reject**: block the tool and tell Claude why
- **Suggest alternative**: block but guide Claude toward what the user wants instead

## Handle clarifying questions

When Claude needs more direction, it calls the `AskUserQuestion` tool. Check if `tool_name == "AskUserQuestion"` to handle it differently.

### Question format

```json
{
  "questions": [
    {
      "question": "How should I format the output?",
      "header": "Format",
      "options": [
        { "label": "Summary", "description": "Brief overview of key points" },
        { "label": "Detailed", "description": "Full explanation with examples" }
      ],
      "multiSelect": false
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `question` | The full question text to display |
| `header` | Short label for the question (max 12 characters) |
| `options` | Array of 2-4 choices, each with `label` and `description` |
| `multiSelect` | If `true`, users can select multiple options |

### Response format

Return an `answers` object mapping each question's `question` field to the selected option's `label`:

```json
{
  "questions": [...],
  "answers": {
    "How should I format the output?": "Summary",
    "Which sections should I include?": "Introduction, Conclusion"
  }
}
```

For multi-select questions, join multiple labels with `", "`.

### Complete example

```python Python
from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import HookMatcher, PermissionResultAllow

def parse_response(response: str, options: list) -> str:
    try:
        indices = [int(s.strip()) - 1 for s in response.split(",")]
        labels = [options[i]["label"] for i in indices if 0 <= i < len(options)]
        return ", ".join(labels) if labels else response
    except ValueError:
        return response

async def handle_ask_user_question(input_data: dict) -> PermissionResultAllow:
    answers = {}

    for q in input_data.get("questions", []):
        print(f"\n{q['header']}: {q['question']}")

        options = q["options"]
        for i, opt in enumerate(options):
            print(f"  {i + 1}. {opt['label']} - {opt['description']}")

        response = input("Your choice: ").strip()
        answers[q["question"]] = parse_response(response, options)

    return PermissionResultAllow(
        updated_input={
            "questions": input_data.get("questions", []),
            "answers": answers,
        }
    )

async def can_use_tool(tool_name: str, input_data: dict, context) -> PermissionResultAllow:
    if tool_name == "AskUserQuestion":
        return await handle_ask_user_question(input_data)
    return PermissionResultAllow(updated_input=input_data)
```

## Limitations

- **60-second timeout**: `canUseTool` callbacks must return within 60 seconds
- **Subagents**: `AskUserQuestion` is not currently available in subagents spawned via the Task tool
- **Question limits**: each `AskUserQuestion` call supports 1-4 questions with 2-4 options each

## Related resources

- [Configure permissions](/docs/en/agent-sdk/permissions): set up permission modes and rules
- [Control execution with hooks](/docs/en/agent-sdk/hooks): run custom code at key points in the agent lifecycle
