<!-- Source: https://platform.claude.com/docs/en/agent-sdk/subagents | Last updated: 2025-01-24 -->

# Subagents in the SDK

Define and invoke subagents to isolate context, run tasks in parallel, and apply specialized instructions in your Claude Agent SDK applications.

---

Subagents are separate agent instances that your main agent can spawn to handle focused subtasks. Use subagents to isolate context for focused subtasks, run multiple analyses in parallel, and apply specialized instructions without bloating the main agent's prompt.

## Overview

You can create subagents in three ways:

- **Programmatically**: use the `agents` parameter in your `query()` options
- **Filesystem-based**: define agents as markdown files in `.claude/agents/` directories
- **Built-in general-purpose**: Claude can invoke the built-in `general-purpose` subagent at any time via the Task tool

## Benefits of using subagents

### Context management
Subagents maintain separate context from the main agent, preventing information overload.

### Parallelization
Multiple subagents can run concurrently, dramatically speeding up complex workflows.

### Specialized instructions and knowledge
Each subagent can have tailored system prompts with specific expertise.

### Tool restrictions
Subagents can be limited to specific tools, reducing the risk of unintended actions.

## Creating subagents

```python Python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async for message in query(
    prompt="Review the authentication module for security issues",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob", "Task"],
        agents={
            "code-reviewer": AgentDefinition(
                description="Expert code review specialist. Use for quality, security, and maintainability reviews.",
                prompt="""You are a code review specialist with expertise in security, performance, and best practices.

When reviewing code:
- Identify security vulnerabilities
- Check for performance issues
- Verify adherence to coding standards
- Suggest specific improvements

Be thorough but concise in your feedback.""",
                tools=["Read", "Grep", "Glob"],
                model="sonnet"
            ),
            "test-runner": AgentDefinition(
                description="Runs and analyzes test suites. Use for test execution and coverage analysis.",
                prompt="""You are a test execution specialist. Run tests and provide clear analysis of results.""",
                tools=["Bash", "Read", "Grep"]
            )
        }
    )
):
    if hasattr(message, "result"):
        print(message.result)
```

```typescript TypeScript
for await (const message of query({
  prompt: "Review the authentication module for security issues",
  options: {
    allowedTools: ['Read', 'Grep', 'Glob', 'Task'],
    agents: {
      'code-reviewer': {
        description: 'Expert code review specialist.',
        prompt: `You are a code review specialist...`,
        tools: ['Read', 'Grep', 'Glob'],
        model: 'sonnet'
      },
      'test-runner': {
        description: 'Runs and analyzes test suites.',
        prompt: `You are a test execution specialist...`,
        tools: ['Bash', 'Read', 'Grep'],
      }
    }
  }
})) {
  if ('result' in message) console.log(message.result);
}
```

### AgentDefinition configuration

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `description` | `string` | Yes | Natural language description of when to use this agent |
| `prompt` | `string` | Yes | The agent's system prompt defining its role and behavior |
| `tools` | `string[]` | No | Array of allowed tool names. If omitted, inherits all tools |
| `model` | `'sonnet' \| 'opus' \| 'haiku' \| 'inherit'` | No | Model override for this agent |

**Note:** Subagents cannot spawn their own subagents. Don't include `Task` in a subagent's `tools` array.

## Invoking subagents

### Automatic invocation
Claude automatically decides when to invoke subagents based on the task and each subagent's `description`.

### Explicit invocation
Mention the subagent by name in your prompt:
```
"Use the code-reviewer agent to check the authentication module"
```

## Tool restrictions

Common tool combinations:

| Use case | Tools | Description |
|:---------|:------|:------------|
| Read-only analysis | `Read`, `Grep`, `Glob` | Can examine code but not modify or execute |
| Test execution | `Bash`, `Read`, `Grep` | Can run commands and analyze output |
| Code modification | `Read`, `Edit`, `Write`, `Grep`, `Glob` | Full read/write access without command execution |
| Full access | All tools | Inherits all tools from parent (omit `tools` field) |

## Resuming subagents

Subagents can be resumed to continue where they left off. To resume:

1. **Capture the session ID**: Extract `session_id` from messages during the first query
2. **Extract the agent ID**: Parse `agentId` from the message content
3. **Resume the session**: Pass `resume: sessionId` in the second query's options

```python Python
import re
import json

def extract_agent_id(text: str) -> str | None:
    match = re.search(r"agentId:\s*([a-f0-9-]+)", text)
    return match.group(1) if match else None

agent_id = None
session_id = None

async for message in query(
    prompt="Use the Explore agent to find all API endpoints in this codebase",
    options=ClaudeAgentOptions(allowed_tools=["Read", "Grep", "Glob", "Task"])
):
    if hasattr(message, "session_id"):
        session_id = message.session_id
    if hasattr(message, "content"):
        content_str = json.dumps(message.content, default=str)
        extracted = extract_agent_id(content_str)
        if extracted:
            agent_id = extracted

# Resume with follow-up
if agent_id and session_id:
    async for message in query(
        prompt=f"Resume agent {agent_id} and list the top 3 most complex endpoints",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Task"],
            resume=session_id
        )
    ):
        if hasattr(message, "result"):
            print(message.result)
```

## Troubleshooting

### Claude not delegating to subagents
1. **Include the Task tool**: subagents are invoked via the Task tool
2. **Use explicit prompting**: mention the subagent by name
3. **Write a clear description**: explain exactly when the subagent should be used

### Filesystem-based agents not loading
Agents defined in `.claude/agents/` are loaded at startup only. Restart the session to load new agent files.

## Related documentation

- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [SDK overview](/docs/en/agent-sdk/overview)
