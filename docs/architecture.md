# Architecture Overview

This document describes the architecture and key design decisions for the Self-Improving Financial Analysis Agent.

## Core Concept

The agent is a **self-modifying coding agent** that evolves by editing its own knowledge files. Unlike traditional agents that rely solely on in-context learning, this agent persists learnings to disk, enabling cross-session improvement.

```
┌─────────────────────────────────────────────────────────────┐
│                    Financial Analysis Agent                  │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Read      │    │   Execute    │    │   Edit/Write  │  │
│  │  knowledge/ │───▶│   pandas     │───▶│   knowledge/  │  │
│  │  for context│    │   code       │    │   to learn    │  │
│  └─────────────┘    └──────────────┘    └───────────────┘  │
│         │                   │                   │           │
│         └───────────────────┴───────────────────┘           │
│                    Agentic Loop                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     knowledge/ directory                     │
│                                                             │
│  dataset_schema.md    - Column definitions, valid values    │
│  examples.md          - Accumulated query examples          │
│  learned/             - Agent-created improvements          │
│    ├── functions.py   - Helper functions (agent edits)      │
│    └── guidelines.md  - Best practices (agent edits)        │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

### 1. File-Based Learning Over In-Context Learning

**Decision**: The agent persists learnings to files rather than relying on conversation history.

**Rationale**:
- **Cross-session persistence**: New agent instances automatically load prior learnings
- **Git-trackable evolution**: Changes to knowledge files create a visible history of agent improvement
- **Reduced context usage**: Knowledge is loaded on-demand rather than accumulating in context
- **Human reviewable**: Learnings can be inspected, edited, or rolled back

**Trade-off**: Slightly more complex than pure in-context learning, but enables true self-improvement.

### 2. Error-Driven Learning

**Decision**: The agent only persists learnings after recovering from an error, not on every successful query.

**Rationale**:
- **Signal quality**: Errors provide clear signal that something was learned
- **Avoids noise**: Prevents accumulation of trivial or redundant learnings
- **Research-backed**: Per "When Can LLMs Actually Correct Their Own Mistakes?" (TACL 2024), self-correction works best with reliable external feedback

**Implementation**: The `ExecutionTrace` tracks `error_recovered` and only triggers learning persistence when true.

### 3. Programmatic Verification Before LLM Judge

**Decision**: Use deterministic programmatic checks before (optionally) falling back to LLM-based evaluation.

**Rationale**:
- **Speed**: Programmatic checks are instant vs. LLM calls
- **Reliability**: Deterministic results, no hallucination risk
- **Cost**: No token usage for verification
- **Research-backed**: Claude Agent SDK recommends "gather-act-verify" pattern with programmatic verification

**Layers**:
1. Execution checks (exceptions, result exists)
2. Data shape checks (empty, columns, nulls)
3. Domain checks (financial rules, accounting identities)
4. LLM judge (optional, for semantic validation)

### 4. Single-Agent Architecture

**Decision**: Use a single Sonnet agent rather than multi-agent orchestration.

**Rationale**:
- **Simplicity**: Easier to understand, debug, and maintain
- **Sufficient capability**: Sonnet handles financial analysis well
- **Lower latency**: No inter-agent communication overhead
- **Lower cost**: Single model invocation per turn

**Trade-off**: For more complex domains, multi-agent might provide better specialization.

### 5. Sandboxed Code Execution

**Decision**: Execute pandas code in a restricted namespace with limited builtins.

**Rationale**:
- **Security**: Prevents arbitrary code execution
- **Reproducibility**: Controlled environment ensures consistent results
- **Safety**: No file system access, network calls, or dangerous operations

**Allowed**:
- pandas, numpy operations
- Basic Python builtins (len, sum, min, max, etc.)
- Learned helper functions

**Blocked**:
- File I/O (open, read, write)
- Network (requests, urllib)
- System (os, subprocess, sys)
- Dangerous builtins (eval, exec, __import__)

## File Structure

```
agemo/
├── agent.py                 # Main agent (~400 lines)
├── verification.py          # Verification pipeline (~550 lines)
├── demo.py                  # Interactive demo
├── knowledge/
│   ├── dataset_schema.md    # Static schema definition
│   ├── examples.md          # Query log (agent-managed)
│   └── learned/
│       ├── functions.py     # Helper functions (agent-managed)
│       └── guidelines.md    # Best practices (agent-managed)
├── docs/
│   ├── architecture.md      # This file
│   ├── verification.md      # Verification system design
│   ├── metrics.md           # Metrics and tracking
│   └── learning.md          # Learning mechanism
└── FUN_company_pl_actuals_dataset.csv  # Financial dataset
```

## Tools Available to Agent

| Tool | Purpose | Used For |
|------|---------|----------|
| `read_file` | Read knowledge files | Loading schema, guidelines, functions |
| `write_file` | Create new files | Rarely used (prefer edit_file) |
| `edit_file` | Modify existing files | Persisting learnings |
| `execute_pandas` | Run pandas code | Data analysis |
| `list_files` | List directory contents | Discovery |

## Model Selection

**Model**: `claude-sonnet-4-20250514`

**Rationale**:
- Balance of capability and speed
- Sufficient for financial data analysis
- Cost-effective for iterative development

**Alternative consideration**: Opus for complex pattern extraction during batch learning (not yet implemented).

## Future Considerations

1. **Batch learning**: Periodically analyze accumulated examples with Opus for deeper pattern extraction
2. **Multi-agent**: Separate agents for retrieval, execution, and learning
3. **Confidence scoring**: Add uncertainty quantification to answers
4. **Human-in-the-loop**: Approval workflow for learning persistence
