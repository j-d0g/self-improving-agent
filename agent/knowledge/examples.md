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

<!-- Improver: Add common mistakes and how to avoid them -->
