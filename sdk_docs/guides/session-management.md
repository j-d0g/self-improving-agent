<!-- Source: https://platform.claude.com/docs/en/agent-sdk/sessions | Last updated: 2025-01-24 -->

# Session Management

Understanding how the Claude Agent SDK handles sessions and session resumption

---

The Claude Agent SDK provides session management capabilities for handling conversation state and resumption. Sessions allow you to continue conversations across multiple interactions while maintaining full context.

## How Sessions Work

When you start a new query, the SDK automatically creates a session and returns a session ID in the initial system message. You can capture this ID to resume the session later.

### Getting the Session ID

```typescript TypeScript
import { query } from "@anthropic-ai/claude-agent-sdk"

let sessionId: string | undefined

const response = query({
  prompt: "Help me build a web application",
  options: {
    model: "claude-sonnet-4-5"
  }
})

for await (const message of response) {
  if (message.type === 'system' && message.subtype === 'init') {
    sessionId = message.session_id
    console.log(`Session started with ID: ${sessionId}`)
  }
  console.log(message)
}

// Later, resume with the saved sessionId
if (sessionId) {
  const resumedResponse = query({
    prompt: "Continue where we left off",
    options: {
      resume: sessionId
    }
  })
}
```

```python Python
from claude_agent_sdk import query, ClaudeAgentOptions

session_id = None

async for message in query(
    prompt="Help me build a web application",
    options=ClaudeAgentOptions(
        model="claude-sonnet-4-5"
    )
):
    if hasattr(message, 'subtype') and message.subtype == 'init':
        session_id = message.data.get('session_id')
        print(f"Session started with ID: {session_id}")
    print(message)

# Later, resume with the saved session_id
if session_id:
    async for message in query(
        prompt="Continue where we left off",
        options=ClaudeAgentOptions(
            resume=session_id
        )
    ):
        print(message)
```

## Resuming Sessions

Use the `resume` option with a session ID to continue a previous conversation:

```typescript TypeScript
const response = query({
  prompt: "Continue implementing the authentication system from where we left off",
  options: {
    resume: "session-xyz",
    model: "claude-sonnet-4-5",
    allowedTools: ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
  }
})

for await (const message of response) {
  console.log(message)
}
```

```python Python
async for message in query(
    prompt="Continue implementing the authentication system from where we left off",
    options=ClaudeAgentOptions(
        resume="session-xyz",
        model="claude-sonnet-4-5",
        allowed_tools=["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
    )
):
    print(message)
```

## Forking Sessions

When resuming a session, you can choose to either continue the original session or fork it into a new branch.

### When to Fork a Session

Forking is useful when you want to:
- Explore different approaches from the same starting point
- Create multiple conversation branches without modifying the original
- Test changes without affecting the original session history
- Maintain separate conversation paths for different experiments

### Forking vs Continuing

| Behavior | `forkSession: false` (default) | `forkSession: true` |
|----------|-------------------------------|---------------------|
| **Session ID** | Same as original | New session ID generated |
| **History** | Appends to original session | Creates new branch from resume point |
| **Original Session** | Modified | Preserved unchanged |
| **Use Case** | Continue linear conversation | Branch to explore alternatives |

### Example: Forking a Session

```typescript TypeScript
// First, capture the session ID
let sessionId: string | undefined

const response = query({
  prompt: "Help me design a REST API",
  options: { model: "claude-sonnet-4-5" }
})

for await (const message of response) {
  if (message.type === 'system' && message.subtype === 'init') {
    sessionId = message.session_id
    console.log(`Original session: ${sessionId}`)
  }
}

// Fork the session to try a different approach
const forkedResponse = query({
  prompt: "Now let's redesign this as a GraphQL API instead",
  options: {
    resume: sessionId,
    forkSession: true,  // Creates a new session ID
    model: "claude-sonnet-4-5"
  }
})

for await (const message of forkedResponse) {
  if (message.type === 'system' && message.subtype === 'init') {
    console.log(`Forked session: ${message.session_id}`)
  }
}

// The original session remains unchanged and can still be resumed
const originalContinued = query({
  prompt: "Add authentication to the REST API",
  options: {
    resume: sessionId,
    forkSession: false,  // Continue original session (default)
    model: "claude-sonnet-4-5"
  }
})
```

```python Python
# First, capture the session ID
session_id = None

async for message in query(
    prompt="Help me design a REST API",
    options=ClaudeAgentOptions(model="claude-sonnet-4-5")
):
    if hasattr(message, 'subtype') and message.subtype == 'init':
        session_id = message.data.get('session_id')
        print(f"Original session: {session_id}")

# Fork the session to try a different approach
async for message in query(
    prompt="Now let's redesign this as a GraphQL API instead",
    options=ClaudeAgentOptions(
        resume=session_id,
        fork_session=True,  # Creates a new session ID
        model="claude-sonnet-4-5"
    )
):
    if hasattr(message, 'subtype') and message.subtype == 'init':
        forked_id = message.data.get('session_id')
        print(f"Forked session: {forked_id}")
```
