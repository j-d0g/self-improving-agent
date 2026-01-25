<!-- Source: https://platform.claude.com/docs/en/agent-sdk/secure-deployment | Last updated: 2025-01-24 -->

# Securely deploying AI agents

A guide to securing Claude Code and Agent SDK deployments with isolation, credential management, and network controls

---

Claude Code and the Agent SDK are powerful tools that can execute code, access files, and interact with external services on your behalf. This guide covers practical ways to secure your deployment.

## What are we protecting against?

Agents can take unintended actions due to prompt injection (instructions embedded in content they process) or model error. Defense in depth is good practice. For example, if an agent processes a malicious file that instructs it to send data to an external server, network controls can block that request entirely.

## Built-in security features

Claude Code includes several security features:

- **Permissions system**: Every tool and bash command can be configured to allow, block, or prompt the user for approval
- **Static analysis**: Before executing bash commands, Claude Code runs static analysis to identify potentially risky operations
- **Web search summarization**: Search results are summarized rather than passing raw content directly into the context
- **Sandbox mode**: Bash commands can run in a sandboxed environment that restricts filesystem and network access

## Security principles

### Security boundaries

For high-security deployments, place sensitive resources (like credentials) outside the boundary containing the agent. Rather than giving an agent direct access to an API key, run a proxy outside the agent's environment that injects the key into requests.

### Least privilege

| Resource | Restriction options |
|----------|---------------------|
| Filesystem | Mount only needed directories, prefer read-only |
| Network | Restrict to specific endpoints via proxy |
| Credentials | Inject via proxy rather than exposing directly |
| System capabilities | Drop Linux capabilities in containers |

### Defense in depth

For high-security environments, layer multiple controls:
- Container isolation
- Network restrictions
- Filesystem controls
- Request validation at a proxy

## Isolation technologies

| Technology | Isolation strength | Performance overhead | Complexity |
|------------|-------------------|---------------------|------------|
| Sandbox runtime | Good | Very low | Low |
| Containers (Docker) | Setup dependent | Low | Medium |
| gVisor | Excellent | Medium/High | Medium |
| VMs (Firecracker, QEMU) | Excellent | High | Medium/High |

### Sandbox runtime

For lightweight isolation without containers, `sandbox-runtime` enforces filesystem and network restrictions at the OS level.

```bash
npm install @anthropic-ai/sandbox-runtime
```

### Containers

A security-hardened container configuration:

```bash
docker run \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  --network none \
  --memory 2g \
  --cpus 2 \
  --pids-limit 100 \
  --user 1000:1000 \
  -v /path/to/code:/workspace:ro \
  agent-image
```

**Key options:**
- `--cap-drop ALL`: Removes Linux capabilities
- `--network none`: Removes all network interfaces
- `--read-only`: Makes the container's root filesystem immutable
- `-v ...:/workspace:ro`: Mounts code read-only

**Avoid mounting sensitive host directories** like `~/.ssh`, `~/.aws`, or `~/.config`.

### gVisor

gVisor addresses kernel vulnerabilities by intercepting system calls in userspace:

```json
// /etc/docker/daemon.json
{
  "runtimes": {
    "runsc": {
      "path": "/usr/local/bin/runsc"
    }
  }
}
```

```bash
docker run --runtime=runsc agent-image
```

## Credential management

### The proxy pattern

Run a proxy outside the agent's security boundary that injects credentials into outgoing requests:

1. The agent never sees the actual credentials
2. The proxy can enforce an allowlist of permitted endpoints
3. The proxy can log all requests for auditing
4. Credentials are stored in one secure location

### Configuring Claude Code to use a proxy

**Option 1: ANTHROPIC_BASE_URL**
```bash
export ANTHROPIC_BASE_URL="http://localhost:8080"
```

**Option 2: HTTP_PROXY / HTTPS_PROXY**
```bash
export HTTP_PROXY="http://localhost:8080"
export HTTPS_PROXY="http://localhost:8080"
```

## Filesystem configuration

### Read-only code mounting

```bash
docker run -v /path/to/code:/workspace:ro agent-image
```

**Files to exclude or sanitize:**
- `.env`, `.env.local` - API keys, database passwords
- `~/.git-credentials` - Git passwords/tokens
- `~/.aws/credentials` - AWS access keys
- `*.pem`, `*.key` - Private keys

### Writable locations

For ephemeral workspaces, use `tmpfs` mounts:

```bash
docker run \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  --tmpfs /workspace:rw,noexec,size=500m \
  agent-image
```

## Further reading

- [Claude Code security documentation](https://code.claude.com/docs/en/security)
- [Hosting the Agent SDK](/docs/en/agent-sdk/hosting)
- [Handling permissions](/docs/en/agent-sdk/permissions)
- [Sandbox runtime](https://github.com/anthropic-experimental/sandbox-runtime)
