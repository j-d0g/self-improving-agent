# Self-Improving Financial Analysis Agent - Design Document

## Overview

A self-improving AI agent that answers financial questions about P&L data using natural language. The agent learns from its interactions by editing its own knowledge files, enabling cross-session improvement.

## Architecture

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
│    ├── functions.py   - Helper functions (agent edits this) │
│    └── guidelines.md  - Best practices (agent edits this)   │
└─────────────────────────────────────────────────────────────┘
```

## Core Concept: Self-Modifying Agent

The key insight is that the learning mechanism IS the agent editing its own files. No separate meta-learner, no batch thresholds, no regex parsing of outputs.

**How it works:**
1. Agent reads `knowledge/` files as context before each query
2. Agent generates and executes pandas code
3. Agent evaluates results and decides if something is worth learning
4. Agent uses `edit_file` tool to modify `knowledge/learned/` files
5. Future sessions (new agent instances) load the modified files

## Tools

The agent has 5 tools:

| Tool | Purpose |
|------|---------|
| `read_file` | Read knowledge files for context |
| `edit_file` | Modify files (find/replace) - primary learning mechanism |
| `write_file` | Create new files if needed |
| `execute_pandas` | Run pandas code against the dataset |
| `list_files` | Explore directory structure |

## Learning Mechanism

### Continuous Learning (No Batch Threshold)

The agent learns immediately when it discovers something useful, rather than waiting for a batch of examples.

**When the agent learns:**
- Discovers a reusable pattern → adds helper function to `functions.py`
- Makes a mistake and fixes it → adds guideline to `guidelines.md`
- Successfully answers a query → logs example to `examples.md`

### File Edit Pattern

Files have marker lines that the agent uses to append content:

```python
# knowledge/learned/functions.py
# ---LEARNING_MARKER---
# Agent adds functions after this line
```

```markdown
<!-- knowledge/learned/guidelines.md -->
<!-- ---LEARNING_MARKER--- -->
<!-- Agent adds guidelines after this line -->
```

## Code Execution

### Sandboxed exec()

Code runs in a restricted namespace with:
- `df` - copy of the dataset (prevents mutation)
- `pd` - pandas library
- Learned functions loaded from `knowledge/learned/functions.py`
- Safe builtins only (no `open`, `eval`, `exec`, `import`)

```python
namespace = {
    "df": self.df.copy(),
    "pd": pd,
    "result": None,
    **self.learned_namespace
}
namespace["__builtins__"] = safe_builtins
exec(code, namespace)
```

## File Structure

```
agemo/
├── agent.py                      # Main agent (~250 lines)
├── demo.py                       # Interactive demo script
├── requirements.txt              # anthropic, pandas, python-dotenv
├── knowledge/
│   ├── dataset_schema.md         # Column definitions (hand-written)
│   ├── examples.md               # Query log (agent-managed)
│   └── learned/
│       ├── functions.py          # Helper functions (agent-managed)
│       └── guidelines.md         # Best practices (agent-managed)
└── FUN_company_pl_actuals_dataset.csv
```

## System Prompt

The agent's system prompt instructs it to:

1. **Always read knowledge files first** before answering queries
2. **Generate pandas code** with result assigned to `result` variable
3. **Validate results** - check if they make sense
4. **Learn and persist** - edit knowledge files when discovering something useful

Key instruction:
> "When you learn something that would help future queries, YOU MUST edit the knowledge/learned/ files to persist that learning. This is how you improve."

## Cross-Session Learning Flow

**Session 1:**
```
User: "What was Q1 2024 revenue for Product A?"

Agent:
1. Reads knowledge/dataset_schema.md
2. Reads knowledge/learned/functions.py (empty)
3. Generates pandas code
4. Executes successfully
5. Realizes quarterly revenue is a common pattern
6. Edits knowledge/learned/functions.py to add helper function
```

**Session 2 (fresh agent instance):**
```
User: "What was Q2 2023 revenue for Product B?"

Agent:
1. Reads knowledge/dataset_schema.md
2. Reads knowledge/learned/functions.py → finds helper function!
3. Uses the learned helper in generated code
4. Executes correctly
```

## Model Selection

| Component | Model | Reason |
|-----------|-------|--------|
| Main agent | claude-sonnet-4-20250514 | Balance of capability and speed |

The architecture supports swapping models easily by changing one line in `agent.py`.

## Design Decisions

### Why Single Agent vs Multi-Agent?

**Chose:** Single agent with file-editing tools
**Rejected:** Multiple sub-agents (Haiku for retrieval, Opus for meta-learning)

**Rationale:**
- Simpler implementation (~250 lines vs ~1000+)
- Easier to debug and understand
- The agent can make learning decisions in context
- No coordination overhead between agents

### Why Continuous vs Batch Learning?

**Chose:** Continuous - learn immediately when useful
**Rejected:** Batch threshold (e.g., every 25 examples)

**Rationale:**
- Simpler implementation
- Faster feedback loop
- No need for separate meta-learning pass
- Agent has full context when deciding to learn

### Why File Editing vs Database?

**Chose:** Markdown/Python files with git versioning
**Rejected:** SQLite, vector stores, Redis

**Rationale:**
- Human-readable and auditable
- Git provides versioning for free
- No additional dependencies
- Easy to inspect what the agent learned

## Usage

```bash
# Activate virtual environment
source .venv/bin/activate

# Run a query
python agent.py "What was Q1 2024 revenue for Product A?"

# Interactive mode
python demo.py -i

# Show learned knowledge
python demo.py --show

# Reset learnings
python demo.py --reset
```

## Verification

To verify cross-session learning:

1. Reset learnings: `python demo.py --reset`
2. Run a query: `python agent.py "What was Q1 2024 revenue?"`
3. Check what was learned: `python demo.py --show`
4. See git diff: `git diff knowledge/`
5. Start fresh session and run similar query
6. Verify learned functions are used

## Limitations & Future Work

### Current Limitations
- Single model (could add Opus for complex analysis)
- No rollback mechanism for bad learnings
- No confidence scoring
- Limited to single CSV dataset

### Potential Enhancements
- Add extended thinking for complex queries
- Implement learning quality validation
- Support multiple datasets
- Add visualization capabilities
