# Project: Financial Analysis Agent

## Overview

This is a coding agent that answers financial questions about P&L data. The core innovation is **cross-session learning**: the agent persists learnings to files so new sessions benefit from past mistakes.

## Key Files

- `agent/agent.py` - Core agent implementation
- `agent/demo.py` - Demo script
- `agent/learning_demo.py` - Cross-session learning demo
- `agent/eval_runner.py` - Evaluation harness
- `agent/knowledge/` - Learning persistence directory

## Architecture

1. **Agentic Loop**: User query → Claude API → Tool calls → Response
2. **Tools**: read_file, execute_pandas, list_files, edit_file
3. **Learning**: On error recovery, agent writes patterns to knowledge/ files

## Running

```bash
cd agent
python agent.py "What was revenue for Product A in 2024?"
python demo.py
python learning_demo.py
python eval_runner.py evals/train.json
```

## Development Notes

- The agent uses Claude's tool calling API
- Code execution is sandboxed (restricted builtins)
- `edit_file` is restricted to `knowledge/` directory only
- Learning is triggered in system prompt Step 5

## Dataset

`FUN_company_pl_actuals_dataset.csv` - P&L actuals for fictional company
- Products: A, B, C, D (no others exist)
- Countries: Australia, Canada, Germany, Japan, United Kingdom, United States
- Years: 2020-2024
