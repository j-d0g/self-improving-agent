---
name: improve
description: Claude Code coaching - analyze usage patterns against best practices, identify underutilized features, and suggest improvements to how you work with Claude.
---

# Optimize

Coach on Claude Code usage - are you using it effectively?

## What to Analyze

### Skills vs Sub-agents vs Hooks

Check if the user is using the right mechanism:

| Mechanism | Purpose | Use when |
|-----------|---------|----------|
| **Skill** | Workflow instructions | Orchestration, multi-step processes, templates |
| **Sub-agent** | Isolated Claude instance | Tool restrictions, fresh context, parallel/background work |
| **Hook** | Automated script | Deterministic automation, no LLM reasoning needed |

**Signs a skill should be a sub-agent:**
- Needs tool restrictions (read-only, no writes)
- Needs isolated context (fresh perspective)
- Should run in background

**Signs something should be a hook:**
- Deterministic (same input → same output)
- Should run automatically on events
- Doesn't need LLM reasoning

### Skill Naming Conventions

- **Actions:** `validate-*`, `generate-*`, `analyze-*` (verb-first for things that do something)
- **Workflows:** `*-workflow`, `*-process` (for multi-step orchestration)
- **Analysis:** `reflect`, `optimize`, `review` (introspective skills)

Avoid generic names like `helper`, `util`, `misc`.

### Prompting Patterns
- Are instructions clear and specific?
- Could tasks be batched or parallelized?
- Are they using plan mode for complex tasks?
- Are they over-specifying or under-specifying?

### Tool Usage
- Are they using the right tools? (e.g., Glob vs Bash find)
- Are sub-agents being used for parallelizable work?
- Are hooks being used for automation?
- Is the scratchpad being used for temp files?

### Repository Setup
- Is there a CLAUDE.md with project conventions?
- Are skills defined for repeatable workflows?
- Is the .claude/ structure well-organized?
- Are there hooks for common operations?

### Workflow Efficiency
- Are they context-switching unnecessarily?
- Could doc-validator prevent rework?
- Are they using /init, /compact, /clear appropriately?
- Is work being persisted properly between sessions?

## Process

1. **Use `/ask-claude`** to get current best practices for the patterns you're evaluating (e.g., `/ask-claude when should I use sub-agents vs skills?`)
2. Compare best practices against observed usage in this conversation
3. Identify gaps and underutilized features
4. Prioritize suggestions by impact

Note: This skill composes with `/ask-claude`. Don't skip step 1.

## Output Format

```
## Usage Analysis

### What You're Doing Well
- [effective pattern observed]

### Opportunities

#### High Impact
- [significant improvement]
  - Current: [what you're doing]
  - Better: [recommended approach]

#### Quick Wins
- [small change, easy to adopt]

### Repository Improvements
- [specific setup suggestion]

### Commands/Features to Try
- [underutilized feature]
```
