# Evaluation Files

This directory contains evaluation datasets for testing the financial analysis agent.

## Files

- `train.json` - Training set with 9 queries (used for development and learning)
- `test.json` - Test set with 9 queries (used for final evaluation)

## JSON Format

Each evaluation is a JSON array of objects with the following fields:

```json
{
  "query": "The natural language question to ask the agent",
  "answer": "The expected answer (used for comparison)"
}
```

## Query Types

**Training set** focuses on:
- Direct lookups (revenue, expenses for specific periods)
- Calculations (YoY growth, margins, percentages)
- Edge cases (non-existent products, unavailable data)

**Test set** focuses on:
- Complex analysis (variance analysis, rolling averages)
- Multi-dimensional queries (product-country-year combinations)
- Pattern recognition (seasonality, outliers)

## Running Evaluations

```bash
cd agent
python eval_runner.py evals/train.json
python eval_runner.py evals/test.json
```

The eval runner sends each query to the agent and compares responses against expected answers.
