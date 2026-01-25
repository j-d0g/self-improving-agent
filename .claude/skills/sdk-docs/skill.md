---
name: sdk-docs
description: Search the Claude Agent SDK documentation to answer questions about building agents with the Python SDK. Use when questions involve agents, tools, MCP, subagents, hooks, sessions, or SDK implementation patterns.
---

# SDK Docs

Search the local Claude Agent SDK documentation (`sdk_docs/`) to answer questions about building agents with the Python SDK.

## Usage

```
/sdk-docs <question>
```

## Examples

```
/sdk-docs how do I create custom tools?
/sdk-docs what are subagents and how do I use them?
/sdk-docs how does session management work?
/sdk-docs how do I add MCP servers to my agent?
/sdk-docs what's the structure of a basic agent?
```

## Behavior

When invoked, search the `sdk_docs/` directory to find relevant documentation and provide a comprehensive answer.

### Search Strategy

1. **Identify the topic** from the user's question
2. **Search relevant files** using Grep and Read:
   - `sdk_docs/python.md` - Python API reference (comprehensive)
   - `sdk_docs/quickstart.md` - Getting started basics
   - `sdk_docs/overview.md` - High-level concepts
   - `sdk_docs/guides/` - Topic-specific guides:
     - `custom-tools.md` - Creating tools
     - `subagents.md` - Spawning sub-agents
     - `mcp.md` - MCP server integration
     - `hooks.md` - Lifecycle hooks
     - `session-management.md` - Session persistence
     - `system-prompts.md` - Prompt engineering
     - `structured-outputs.md` - Output schemas
     - `streaming-input.md` - Streaming responses
     - `cost-tracking.md` - Usage tracking
     - `permissions.md` - Tool permissions
     - `hosting.md` - Deployment options
     - `secure-deployment.md` - Security practices

3. **Provide answer** with:
   - Direct answer to the question
   - Relevant code examples from the docs
   - File references for further reading

### Implementation

```python
# Search pattern for topic
Grep(pattern="<topic keywords>", path="sdk_docs/", output_mode="files_with_matches")

# Read the most relevant file(s)
Read(file_path="sdk_docs/guides/<relevant-guide>.md")
Read(file_path="sdk_docs/python.md")  # For API details

# Synthesize answer from documentation
```

## Topics Covered

- Agent creation and configuration
- Custom tool definitions
- MCP server integration
- Subagent orchestration
- Session management and persistence
- Hooks and lifecycle events
- Streaming responses
- Structured outputs
- Cost tracking
- Permissions and security
- Deployment and hosting

## Notes

- This skill searches LOCAL documentation in `sdk_docs/`, not the web
- For questions about Claude Code CLI (not the Python SDK), use `/ask-claude` instead
- The `sdk_docs/python.md` file is the most comprehensive API reference
