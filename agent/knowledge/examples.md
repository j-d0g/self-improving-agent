# Query Examples

This file contains example queries and patterns for the learner to reference.

## Positive Examples

### Comparing Products on Multiple Metrics

**Query**: "Find all months where Product A outperformed Product B in revenue but underperformed in gross margin, broken down by country"

**Interpretation**: Find time periods and countries where:
1. Product A has higher total revenue than Product B
2. Product A has lower gross margin (Revenue - COGS) than Product B

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Get revenue by Product, Country, Year, Period
revenue = (
    df[df['FSLine Statement L1'] == 'Net Revenue']
    .groupby(['Product', 'Country', 'Fiscal Year', 'Fiscal Period'])['Amount in USD']
    .sum()
    .reset_index()
    .rename(columns={'Amount in USD': 'Revenue'})
)

# Get COGS by Product, Country, Year, Period
cogs = (
    df[df['FSLine Statement L1'] == 'Cost of Goods Sold']
    .groupby(['Product', 'Country', 'Fiscal Year', 'Fiscal Period'])['Amount in USD']
    .sum()
    .reset_index()
    .rename(columns={'Amount in USD': 'COGS'})
)

# Merge and calculate gross margin
metrics = revenue.merge(cogs, on=['Product', 'Country', 'Fiscal Year', 'Fiscal Period'])
metrics['Gross_Margin'] = metrics['Revenue'] - metrics['COGS']

# Pivot to compare Product A vs B
pivot_rev = metrics.pivot_table(
    index=['Country', 'Fiscal Year', 'Fiscal Period'],
    columns='Product',
    values='Revenue'
).reset_index()

pivot_margin = metrics.pivot_table(
    index=['Country', 'Fiscal Year', 'Fiscal Period'],
    columns='Product',
    values='Gross_Margin'
).reset_index()

# Merge pivots
comparison = pivot_rev.merge(
    pivot_margin,
    on=['Country', 'Fiscal Year', 'Fiscal Period'],
    suffixes=('_rev', '_margin')
)

# Filter: A > B in revenue AND A < B in gross margin
result = comparison[
    (comparison[('A', '')] if ('A', '') in comparison.columns else comparison['A_rev'] > comparison['B_rev']) &
    (comparison['A_margin'] < comparison['B_margin'])
]

print(result)
```

**Key insight**:
1. Aggregate by filtering on `FSLine Statement L1`, not by accessing non-existent columns
2. Use pivot tables to compare products side-by-side
3. The dataset uses `Fiscal Period` (1-12), not 'Month'

---

## Negative Examples

### MISTAKE: Using Non-Existent Column Names

**Query**: Any query involving revenue or COGS

**Wrong approach**:
```python
# WRONG - these columns don't exist!
df['Revenue']
df['COGS']
df['Gross_Margin'] = df['Revenue'] - df['COGS']
```

**Why it fails**: The dataset has no direct 'Revenue' or 'COGS' columns. Data is stored in a normalized format with `FSLine Statement L1` indicating the financial category and `Amount in USD` containing the values.

**Correct approach**:
```python
# CORRECT - filter by category, then aggregate
revenue = df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD'].sum()
cogs = df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD'].sum()
gross_margin = revenue - cogs
```

**How to recognize this trap**: Any time you need revenue/COGS/expenses, you must filter by `FSLine Statement L1` first.

---

### MISTAKE: Not Executing Code (Providing Untested Code)

**Query**: Any query requiring actual data results

**Wrong approach**:
```python
# Writing code in the response but never running it
# "Here's the code that would do this..."
```

**Why it fails**: The user asked for results, not code. Untested code often has bugs. The learner should ALWAYS execute code using the Bash tool to verify it works and provide actual results.

**Correct approach**:
1. Write the code
2. Execute it using the Bash tool
3. Verify the output
4. Present the actual results to the user

**How to recognize this trap**: If your answer contains code but you haven't made any tool calls, you haven't actually answered the question.

---

### MISTAKE: Using 'Month' Column That Doesn't Exist

**Query**: "Find months where..."

**Wrong approach**:
```python
# WRONG - no 'Month' column exists
df.groupby(['Product', 'Country', 'Month'])
```

**Why it fails**: The dataset has `Fiscal Period` (1-12) and `Fiscal Quarter`, but no 'Month' column.

**Correct approach**:
```python
# CORRECT - use Fiscal Year + Fiscal Period for unique month identification
df.groupby(['Product', 'Country', 'Fiscal Year', 'Fiscal Period'])
```

**How to recognize this trap**: When users say "month", translate to `Fiscal Period` (or combine with `Fiscal Year` for unique months across years).
