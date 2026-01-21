# Financial Analysis Agent

A coding agent that answers financial questions about P&L data using pandas. Features cross-session learning to improve over time.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
echo "ANTHROPIC_API_KEY=your-key" > .env
# Edit .env and add your actual ANTHROPIC_API_KEY
```

## Architecture

```
agent/
├── agent.py           # Core agent: agentic loop, tools, learning
├── demo.py            # Demo script for basic agent capabilities
├── learning_demo.py   # Demo for cross-session learning
├── eval_runner.py     # Evaluation harness for running test queries
├── data/
│   └── FUN_company_pl_actuals_dataset.csv
└── knowledge/
    ├── schema.md           # Schema documentation
    ├── examples.md         # Query patterns (agent learns here)
    └── functions.py        # Reusable functions (agent learns here)
```

### Core Components

**Agent Loop** (`agent.py`)
- Uses Claude API with tool calling
- Tools: `read_file`, `execute_pandas`, `list_files`, `edit_file`
- Sandboxed code execution for safety

**Cross-Session Learning**
- Agent writes learnings to `knowledge/` files via `edit_file` tool
- New agent instances load these files and benefit from past sessions
- Learning triggered when agent recovers from errors

**Execution Metrics**
- Tracks tokens, tool calls, errors, and learning events
- Aggregated via `AgentMetrics` class

## Usage

### Interactive Mode
```bash
cd agent
python agent.py
```

### Single Query
```bash
cd agent
python agent.py "What was the total revenue for Product A in Q1 2024?"
```

### Demo
```bash
cd agent
python demo.py           # Scripted demo
python demo.py -i        # Interactive mode
```

### Cross-Session Learning Demo
```bash
cd agent
python learning_demo.py
```

### Run Evaluations
```bash
cd agent
python eval_runner.py evals/train.json
python eval_runner.py evals/test.json
```

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read knowledge files, schema, learned patterns |
| `execute_pandas` | Execute pandas code against the dataset (sandboxed) |
| `list_files` | List files in a directory |
| `edit_file` | Append to knowledge files (for learning persistence) |

## Dataset

The agent analyzes `FUN_company_pl_actuals_dataset.csv`:
- **Products:** A, B, C, D
- **Countries:** Australia, Canada, Germany, Japan, UK, US
- **Years:** 2020-2024
- **Metrics:** Revenue, COGS, OPEX, Other Income/Expenses

See `knowledge/dataset_schema.md` for full schema.

## Learning System

When the agent encounters an error and recovers:
1. It analyzes what went wrong
2. Generalizes the fix for similar queries
3. Persists the learning to knowledge files

Knowledge files:
- `examples.md` - Query patterns with working code
- `functions.py` - Reusable helper functions
