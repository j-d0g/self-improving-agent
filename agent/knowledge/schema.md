# P&L Dataset Schema

This file documents the structure and valid values in the P&L dataset.

## Dataset Location

`data/FUN_company_pl_actuals_dataset.csv`

## Columns

| Column | Description |
|--------|-------------|
| Product | Product identifier |
| Country | Country name |
| Currency | Local currency code (AUD, CAD, EUR, JPY, GBP, USD) |
| Fiscal Year | Year (numeric) |
| Fiscal Quarter | Q1, Q2, Q3, Q4 |
| Fiscal Period | Period within quarter |
| FSLine Statement L1 | Top-level financial category |
| FSLine Statement L2 | Detailed line item |
| Amount in USD | USD value |
| Amount in Local Currency | Local currency value |
| Version | Data version (always "Actuals" in this dataset) |

**IMPORTANT - Column Names Are Case-Sensitive AND Full Names!**
- Use `df['Country']` NOT `df['country']`
- Use `df['Fiscal Year']` NOT `df['fiscal_year']`
- Use `df['FSLine Statement L2']` NOT `df['L2']`
- Use `df['Amount in USD']` NOT `df['Amount']`
- All column names use Title Case with spaces - NO abbreviations

## Valid Values

### Products
- A, B, C, D (only these four exist - no others)

### Countries
- Australia, Canada, Germany, Japan, United Kingdom, United States

### Currencies (by Country)
| Country | Currency Code |
|---------|---------------|
| Australia | AUD |
| Canada | CAD |
| Germany | EUR |
| Japan | JPY |
| United Kingdom | GBP |
| United States | USD |

### Years
- 2020, 2021, 2022, 2023, 2024

### FSLine Statement L1 (Top-level categories)
- Net Revenue
- Cost of Goods Sold
- OPEX (**NOT** "Operating Expenses" - use exactly `'OPEX'`)
- Other Income/Expenses

### FSLine Statement L2 (Detailed line items)

**IMPORTANT**: When filtering by L2, use the exact values below. There is NO L2 value called "Revenue" or "Cost of Goods Sold" - those are L1 values.

| L1 Category | L2 Line Items |
|-------------|---------------|
| Net Revenue | `Gross Revenue`, `Returns and Refunds`, `Revenue Adjustment` |
| Cost of Goods Sold | `Direct Labor`, `Direct Materials`, `Manufacturing Overhead` |
| OPEX | `General & Administrative`, `Headcount Expenses`, `IT Expenses`, `Marketing Expenses`, `R&D Expenses`, `Sales Expenses` |
| Other Income/Expenses | `Foreign Exchange Gain/Loss`, `Interest Expense`, `Interest Income` |

**To get Revenue using L2** (if L1 filtering is not enough):
```python
revenue = df[df['FSLine Statement L2'].isin(['Gross Revenue', 'Revenue Adjustment'])]['Amount in USD'].sum()
```

**To get COGS using L2**:
```python
cogs = df[df['FSLine Statement L2'].isin(['Direct Labor', 'Direct Materials', 'Manufacturing Overhead'])]['Amount in USD'].sum()
```

**To get OPEX using L2**:
```python
opex = df[df['FSLine Statement L2'].isin([
    'General & Administrative', 'Headcount Expenses', 'IT Expenses',
    'Marketing Expenses', 'R&D Expenses', 'Sales Expenses'
])]['Amount in USD'].sum()
```

### Column Name Reference
**IMPORTANT**: The dataset does NOT have columns named 'Revenue' or 'COGS'.
The correct column names are:
- `FSLine Statement L1` - for the financial category (e.g., 'Net Revenue', 'Cost of Goods Sold')
- `FSLine Statement L2` - for detailed line items
- `Amount in USD` - for the actual numeric values

To get revenue: `df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD']`
To get COGS: `df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD']`

## Profitability Calculations

### Gross Margin / Gross Profit
**Formula**: Gross Margin = Net Revenue - Cost of Goods Sold

```python
# Calculate gross margin for a filtered scope
revenue = df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD'].sum()
cogs = df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD'].sum()
gross_margin = revenue - cogs
```

### Gross Margin by Product/Country/Period
When comparing products, aggregate by the grouping columns first:

```python
# Example: Get revenue by Product and Country
revenue_by_group = (
    df[df['FSLine Statement L1'] == 'Net Revenue']
    .groupby(['Product', 'Country', 'Fiscal Year', 'Fiscal Period'])['Amount in USD']
    .sum()
    .reset_index()
)
```

### Profit Margin (Operating Profit Margin)
**Formula**: Profit Margin = (Revenue - COGS - OPEX) / Revenue × 100

```python
import numpy as np

# Calculate profit margin for grouped data
# Step 1: Get aggregated data by product-country-year
revenue_df = df[df['FSLine Statement L1'] == 'Net Revenue'].groupby(
    ['Product', 'Country', 'Fiscal Year']
)['Amount in USD'].sum().reset_index(name='Revenue')

cogs_df = df[df['FSLine Statement L1'] == 'Cost of Goods Sold'].groupby(
    ['Product', 'Country', 'Fiscal Year']
)['Amount in USD'].sum().reset_index(name='COGS')

opex_df = df[df['FSLine Statement L1'] == 'OPEX'].groupby(
    ['Product', 'Country', 'Fiscal Year']
)['Amount in USD'].sum().reset_index(name='OPEX')

# Step 2: Merge
merged = revenue_df.merge(cogs_df, on=['Product', 'Country', 'Fiscal Year'], how='outer')
merged = merged.merge(opex_df, on=['Product', 'Country', 'Fiscal Year'], how='outer')
merged = merged.fillna(0)

# Step 3: Calculate profit and margin
merged['Profit'] = merged['Revenue'] - merged['COGS'] - merged['OPEX']
merged['Profit_Margin'] = np.where(
    merged['Revenue'] != 0,
    merged['Profit'] / merged['Revenue'] * 100,
    0
)
```

### Year-over-Year Changes
To calculate YoY changes and flag significant deltas:

```python
# Calculate YoY change for a metric (e.g., profit margin)
def calculate_yoy_change(group):
    group = group.sort_values('Fiscal Year')
    group['Prev_Value'] = group['Profit_Margin'].shift(1)
    group['YoY_Change'] = group['Profit_Margin'] - group['Prev_Value']
    return group

# Apply to each product-country combination
# NOTE: Use include_groups=False to avoid FutureWarning in newer pandas
result = merged.groupby(['Product', 'Country'], group_keys=False).apply(
    calculate_yoy_change, include_groups=False
)

# Flag significant changes (e.g., > 5 percentage points)
result['Significant_Change'] = result['YoY_Change'].abs() > 5
```

## Edge Cases

### No Abbreviated Column Names (L2, Amount, etc.)
**Trigger**: Code uses `df['L2']`, `df['L1']`, or `df['Amount']`
**Reality**: The dataset uses full, descriptive column names - NOT abbreviations
**Correct approach**: Always use full column names:
- `df['FSLine Statement L2']` not `df['L2']`
- `df['FSLine Statement L1']` not `df['L1']`
- `df['Amount in USD']` not `df['Amount']`
- If unsure, run `df.columns.tolist()` first

### No 'Month' Column
**Trigger**: Query asks about "months"
**Reality**: The dataset has `Fiscal Period` (1-12) and `Fiscal Quarter`, but no 'Month' column
**Correct approach**: Use `Fiscal Period` as the month identifier, or combine `Fiscal Year` + `Fiscal Period` for unique months

### No Direct Revenue/COGS Columns
**Trigger**: Code attempts to access `df['Revenue']` or `df['COGS']`
**Reality**: These columns don't exist
**Correct approach**: Filter by `FSLine Statement L1` and aggregate `Amount in USD`:
```python
revenue = df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD'].sum()
cogs = df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD'].sum()
```

### Foreign Exchange Impact Analysis
**Trigger**: Query asks about FX impact, currency effects, or foreign exchange
**Reality**: The dataset has `Amount in Local Currency` and `Amount in USD` columns, plus an explicit `Foreign Exchange Gain/Loss` line item under Other Income/Expenses

**WRONG approach** - Do NOT calculate FX variance as difference between local and USD amounts:
```python
# WRONG - you cannot meaningfully subtract amounts in different currencies!
df['FX_Variance'] = np.abs(df['Amount in USD'] - df['Amount in Local Currency'])
```

**CORRECT approach** - Use the Foreign Exchange Gain/Loss line item:
```python
# CORRECT - use the explicit FX line item
fx_impact = df[df['FSLine Statement L2'] == 'Foreign Exchange Gain/Loss'].groupby(
    ['Country', 'Fiscal Year']
)['Amount in USD'].sum()

print(fx_impact)
```

This gives you the actual recorded FX gains/losses by country and year.

### OPEX L1 Value is 'OPEX' Not 'Operating Expenses'
**Trigger**: Query asks about operating expenses, OPEX, or operational costs
**Reality**: The FSLine Statement L1 value is `'OPEX'`, not `'Operating Expenses'`
**Response**: Always filter with `df[df['FSLine Statement L1'] == 'OPEX']`

```python
# WRONG - returns empty DataFrame!
df[df['FSLine Statement L1'] == 'Operating Expenses']

# CORRECT
df[df['FSLine Statement L1'] == 'OPEX']
```

The actual L1 values are: `'Cost of Goods Sold'`, `'Net Revenue'`, `'OPEX'`, `'Other Income/Expenses'`

### No 'date' Column - Use Fiscal Year/Quarter/Period
**Trigger**: Query asks about dates, time series, or seasonal patterns
**Reality**: The dataset does NOT have a 'date' column. It uses separate columns for fiscal time periods.
**Response**: Use `Fiscal Year`, `Fiscal Quarter`, and `Fiscal Period` columns instead

```python
# WRONG - KeyError!
df['date'] = pd.to_datetime(df['date'])
df['month'] = df['date'].dt.month

# CORRECT - use the fiscal columns directly
# Fiscal Year: 2020, 2021, 2022, 2023, 2024
# Fiscal Quarter: Q1, Q2, Q3, Q4
# Fiscal Period: 2020-01, 2020-02, ... 2024-12 (string format)
df.groupby(['Fiscal Year', 'Fiscal Quarter'])['Amount in USD'].sum()
```

### L1 is 'Net Revenue' Not 'Revenue'
**Trigger**: Query asks about revenue
**Reality**: The FSLine Statement L1 value is `'Net Revenue'`, not `'Revenue'`
**Response**: Always use `'Net Revenue'` for L1 filtering

```python
# WRONG - returns empty DataFrame!
df[df['FSLine Statement L1'] == 'Revenue']

# CORRECT
df[df['FSLine Statement L1'] == 'Net Revenue']
```

### No matplotlib Available
**Trigger**: Code attempts to import matplotlib for visualization
**Reality**: matplotlib is not installed in the execution environment
**Response**: Use text-based output instead of visualizations. Present data in tabular format using pandas pivot tables or formatted print statements.

```python
# WRONG - ModuleNotFoundError!
import matplotlib.pyplot as plt
plt.figure(figsize=(12, 6))

# CORRECT - use text-based output
pivot = df.pivot_table(index='Fiscal Quarter', columns='Product', values='Amount in USD')
print(pivot)
```
