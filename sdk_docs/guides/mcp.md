<!-- Source: https://platform.claude.com/docs/en/agent-sdk/mcp | Last updated: 2025-01-24 -->

# Connect to external tools with MCP

Configure MCP servers to extend your agent with external tools. Covers transport types, tool search for large tool sets, authentication, and error handling.

---

The Model Context Protocol (MCP) is an open standard for connecting AI agents to external tools and data sources. With MCP, your agent can query databases, integrate with APIs like Slack and GitHub, and connect to other services without writing custom tool implementations.

## Quickstart

```typescript TypeScript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Use the docs MCP server to explain what hooks are in Claude Code",
  options: {
    mcpServers: {
      "claude-code-docs": {
        type: "http",
        url: "https://code.claude.com/docs/mcp"
      }
    },
    allowedTools: ["mcp__claude-code-docs__*"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

options = ClaudeAgentOptions(
    mcp_servers={
        "claude-code-docs": {
            "type": "http",
            "url": "https://code.claude.com/docs/mcp"
        }
    },
    allowed_tools=["mcp__claude-code-docs__*"]
)

async for message in query(prompt="Use the docs MCP server to explain what hooks are in Claude Code", options=options):
    if isinstance(message, ResultMessage) and message.subtype == "success":
        print(message.result)
```

## Allow MCP tools

MCP tools require explicit permission before Claude can use them.

### Tool naming convention

MCP tools follow the naming pattern `mcp__<server-name>__<tool-name>`. For example, a GitHub server named `"github"` with a `list_issues` tool becomes `mcp__github__list_issues`.

### Grant access with allowedTools

```typescript
options: {
  mcpServers: { /* your servers */ },
  allowedTools: [
    "mcp__github__*",              // All tools from the github server
    "mcp__db__query",              // Only the query tool from db server
    "mcp__slack__send_message"     // Only send_message from slack server
  ]
}
```

### Alternative: Change the permission mode

- `permissionMode: "acceptEdits"`: Automatically approves tool usage
- `permissionMode: "bypassPermissions"`: Skips all safety prompts (use with caution)

## Transport types

### stdio servers

Local processes that communicate via stdin/stdout:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

### HTTP/SSE servers

For cloud-hosted MCP servers and remote APIs:

```json
{
  "mcpServers": {
    "remote-api": {
      "type": "sse",
      "url": "https://api.example.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    }
  }
}
```

### SDK MCP servers

Define custom tools directly in your application code. See the custom tools guide for details.

## MCP tool search

When you have many MCP tools configured, tool search runs in auto mode by default. It activates when your MCP tool descriptions would consume more than 10% of the context window.

Control with the `ENABLE_TOOL_SEARCH` environment variable:

| Value | Behavior |
|:------|:---------|
| `auto` | Activates when MCP tools exceed 10% of context (default) |
| `auto:5` | Activates at 5% threshold |
| `true` | Always enabled |
| `false` | Disabled, all MCP tools loaded upfront |

## Authentication

### Pass credentials via environment variables

```python Python
options = ClaudeAgentOptions(
    mcp_servers={
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]
            }
        }
    },
    allowed_tools=["mcp__github__list_issues"]
)
```

### HTTP headers for remote servers

```python Python
options = ClaudeAgentOptions(
    mcp_servers={
        "secure-api": {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {
                "Authorization": f"Bearer {os.environ['API_TOKEN']}"
            }
        }
    },
    allowed_tools=["mcp__secure-api__*"]
)
```

## Error handling

The SDK emits a `system` message with subtype `init` at the start of each query. Check the `status` field to detect connection failures:

```typescript TypeScript
for await (const message of query({
  prompt: "Process data",
  options: { mcpServers: { "data-processor": dataServer } }
})) {
  if (message.type === "system" && message.subtype === "init") {
    const failedServers = message.mcp_servers.filter(
      s => s.status !== "connected"
    );
    if (failedServers.length > 0) {
      console.warn("Failed to connect:", failedServers);
    }
  }
}
```

## Troubleshooting

### Server shows "failed" status
- **Missing environment variables**: Ensure required tokens and credentials are set
- **Server not installed**: For `npx` commands, verify the package exists
- **Invalid connection string**: For database servers, verify the connection string format
- **Network issues**: For remote HTTP/SSE servers, check the URL is reachable

### Tools not being called
Check that you've granted permission with `allowedTools` or by changing the permission mode.

## Related resources

- **Custom tools guide**: Build your own MCP server
- **Permissions**: Control which MCP tools your agent can use
- **MCP server directory**: Browse available MCP servers
