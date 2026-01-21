# Self-Improving Financial Analysis Agent

An AI agent that answers financial questions about P&L data and **learns from its mistakes**. The agent generates pandas code, logs detailed session traces, and improves its knowledge base through a three-agent pipeline.

## Key Feature: Cross-Session Learning

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Learner   │────▶│  Evaluator  │────▶│  Improver   │
│   (Haiku)   │     │   (Opus)    │     │  (Sonnet)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
  Session logs      Critiques &         Updates to
  with reflection   improvements       knowledge base
```

1. **Learner** answers queries and logs its process, errors, and self-reflection
2. **Evaluator** critiques logs for correctness and efficiency issues
3. **Improver** applies fixes to schema, examples, and helper functions

New learner sessions benefit from accumulated knowledge.

## Setup

```bash
cd agent
pip install -r requirements.txt

# Create .env with your API key
echo "ANTHROPIC_API_KEY=your-key" > .env
```

## Usage

### Interactive Mode
```bash
cd agent
python demo.py -i
```

### Single Query
```bash
cd agent
python agent.py "What was revenue for Product A in Q1 2024?"
```

### Run the Learning Pipeline (Claude Code)

```bash
# 1. Run learner on a query
claude "Use the learner agent to answer: What was gross revenue for Product B in 2023?"

# 2. Evaluate the session
claude "Use the evaluator agent to critique the latest session log"

# 3. Apply improvements
claude "Use the improver agent to implement the recommended changes"
```

## Project Structure

```
agent/
├── agent.py                 # Core agent implementation
├── demo.py                  # Demo script
├── eval_runner.py           # Batch evaluation harness
├── data/
│   └── FUN_company_pl_actuals_dataset.csv
├── evals/
│   ├── train.json           # Training queries
│   └── test.json            # Test queries
├── knowledge/               # Learning artifacts
│   ├── schema.md            # Dataset documentation
│   ├── examples.md          # Query patterns
│   ├── functions.py         # Reusable helpers
│   └── learnings/           # Session logs
└── .claude/
    └── agents/
        ├── learner.md       # Query answering agent
        ├── evaluator.md     # Critique agent
        └── improver.md      # Knowledge updater
```

## How Learning Works

### Session Logs

Every query produces a structured log in `knowledge/learnings/`:

```markdown
<query>What was revenue for Product E?</query>

<interpretation>...</interpretation>

<process>Step-by-step execution...</process>

<answer>Product E does not exist...</answer>

<errors>KeyError when filtering...</errors>

<root_cause_analysis>
Missing validation for product names...
</root_cause_analysis>

<suggested_improvements>
Add product validation to schema.md...
</suggested_improvements>
```

### Knowledge Base

The learner reads these files before answering:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Column definitions, valid values, rules |
| `knowledge/examples.md` | Query patterns with working code |
| `knowledge/functions.py` | Reusable helper functions |

The improver updates these based on evaluator feedback.

## Dataset

`FUN_company_pl_actuals_dataset.csv`:
- **21,600 rows** of P&L data
- **Years**: 2020-2024
- **Products**: A, B, C, D (no others exist)
- **Countries**: Australia, Canada, Germany, Japan, UK, US
- **Metrics**: Revenue, COGS, OPEX, Other Income/Expenses

## Example Queries

- "What was Gross Revenue for Product A in Q1 2024?"
- "Which product had the highest operating margin in 2023?"
- "Calculate year-over-year OPEX growth between 2022 and 2023"
- "What was revenue for Product E?" *(trick question - doesn't exist)*

## Trace Logging

Every query logs a JSON trace to `agent/logs/` with:
- Agent version (git commit)
- Full turn history (thinking + tool calls)
- Token usage
- Final answer

```json
{
  "agent_version": {"commit": "abc123", "dirty": false},
  "query": "...",
  "turns": [
    {"thinking": "...", "tool_calls": [...]}
  ],
  "final_answer": "..."
}
```
