# Financial Analysis Agent

An AI agent that answers financial questions about P&L data using natural language. The agent generates and executes pandas code with programmatic verification and comprehensive metrics tracking.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Financial Analysis Agent                  │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Read      │    │   Execute    │    │   Verify &    │  │
│  │  knowledge/ │───▶│   pandas     │───▶│   Track       │  │
│  │  for context│    │   code       │    │   Metrics     │  │
│  └─────────────┘    └──────────────┘    └───────────────┘  │
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
- `metrics` - Display session metrics
- `quit` - Exit

## Features

### Programmatic Verification
The agent uses a 4-layer verification pipeline:
1. **Execution Layer**: Catches exceptions, validates result exists
2. **Data Shape Layer**: Validates DataFrames (not empty, correct columns)
3. **Financial Domain Layer**: Domain-specific checks (revenue positive, margins valid)
4. **Exception Classification**: Semantic analysis of errors for recovery hints

### Metrics Tracking
Every query is tracked with:
- Success/failure status
- Number of code attempts
- Error categories encountered
- Recovery success rate
- Verification failures

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent with tool loop |
| `demo.py` | Interactive demo script |
| `verification.py` | 4-layer verification pipeline |
| `knowledge/dataset_schema.md` | Column definitions, valid values |

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
