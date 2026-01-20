# Self-Improving Financial Analysis Agent

A self-improving AI agent that answers financial questions about P&L data using natural language. The agent learns from its mistakes and persists knowledge across sessions by editing its own knowledge files.

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

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API key:**
   Create a `.env` file in the project root:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

3. **Ensure the dataset is present:**
   The file `FUN_company_pl_actuals_dataset.csv` should be in the project root.

## Usage

### Interactive Mode
```bash
python demo.py -i
```

### Run Scripted Demo
```bash
python demo.py
```

### Single Query
```bash
python agent.py "What was the total revenue for Product A in Q1 2024?"
```

### Commands in Interactive Mode
- Type your question to ask the agent
- `show` - Display current learned knowledge
- `reset` - Reset all learned knowledge
- `quit` - Exit

## How Self-Improvement Works

1. **Every query**: Agent reads `knowledge/` files for context
2. **Executes code**: Generates and runs pandas code against the dataset
3. **Learns from mistakes**: When the agent discovers something useful, it edits:
   - `knowledge/learned/functions.py` - Adds reusable helper functions
   - `knowledge/learned/guidelines.md` - Adds best practices
   - `knowledge/examples.md` - Logs successful query patterns

4. **Future sessions**: New agent instances load the persisted knowledge

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent with tool loop (~250 lines) |
| `demo.py` | Interactive demo script |
| `knowledge/dataset_schema.md` | Column definitions, valid values |
| `knowledge/learned/functions.py` | Agent-created helper functions |
| `knowledge/learned/guidelines.md` | Agent-created best practices |
| `knowledge/examples.md` | Query log |

## Dataset

The agent analyzes `FUN_company_pl_actuals_dataset.csv`:
- **21,600 rows** of financial data
- **5 years**: 2020-2024
- **4 products**: Product A, B, C, D
- **6 countries**: Australia, Canada, Germany, Japan, UK, US
- **Financial categories**: Net Revenue, COGS, OPEX, Other Income/Expenses

## Example Queries

- "What was the Gross Revenue for Product A in Q1 2024?"
- "Calculate the operating margin for Product B in 2023"
- "Which product had the highest revenue in Q4 2023?"
- "What was the year-over-year change in OPEX between 2022 and 2023?"

## Demo: Cross-Session Learning

**Session 1:**
```
You: What was Q1 2024 revenue for Product A?
Agent: [Makes mistake with quarter filtering, learns, adds helper function]
```

**Session 2 (restart agent):**
```
You: What was Q2 2023 revenue for Product B?
Agent: [Uses learned helper function, answers correctly]
```

Check `knowledge/learned/` files to see what the agent learned!
