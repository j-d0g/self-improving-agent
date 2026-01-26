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
| Version | Data version (always "Actuals" in this dataset - note the 's'!) |

**IMPORTANT - Column Names Are Case-Sensitive AND Full Names!**
- Use `df['Country']` NOT `df['country']`
- Use `df['Fiscal Year']` NOT `df['fiscal_year']`
- Use `df['FSLine Statement L2']` NOT `df['L2']`
- Use `df['Amount in USD']` NOT `df['Amount']`
- All column names use Title Case with spaces - NO abbreviations

## Valid Values

### Products
- `Product A`, `Product B`, `Product C`, `Product D` (only these four exist - no others)

**IMPORTANT**: Product values include the word "Product" - they are NOT just letters!
```python
# WRONG - these won't match anything!
df[df['Product'] == 'A']
df['Product'].isin(['A', 'B'])

# CORRECT - use full product names
df[df['Product'] == 'Product A']
df['Product'].isin(['Product A', 'Product B'])
```

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
# CRITICAL: Use include_groups=False to avoid FutureWarning in newer pandas
result = merged.groupby(['Product', 'Country'], group_keys=False).apply(
    calculate_yoy_change, include_groups=False
)

# Flag significant changes (e.g., > 5 percentage points)
result['Significant_Change'] = result['YoY_Change'].abs() > 5
```

### Alternative: Pivot Table Approach for Multi-Metric Calculations
When calculating metrics like profit margin across multiple dimensions, you can use pivot_table:

```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Pivot to get L1 categories as columns
pivot_df = df.pivot_table(
    index=['Product', 'Country', 'Fiscal Year'],
    columns='FSLine Statement L1',
    values='Amount in USD',
    aggfunc='sum'
).reset_index()

# Now calculate metrics directly (column names match L1 values!)
pivot_df['Net_Income'] = pivot_df['Net Revenue'] - pivot_df['Cost of Goods Sold'] - pivot_df['OPEX']
pivot_df['Profit_Margin'] = (pivot_df['Net_Income'] / pivot_df['Net Revenue'] * 100).round(2)

# CRITICAL: Don't use 'Revenue' - the column is named 'Net Revenue' after pivot!
# CRITICAL: Don't use 'Operating Expenses' - the column is named 'OPEX' after pivot!
```

**Trade-offs**:
- **Pivot approach**: Cleaner syntax, all L1 values become columns, but column names must exactly match L1 values
- **Merge approach**: More explicit, better for complex filtering, easier to debug

## Edge Cases

### Always Check Columns First - Don't Assume
**Trigger**: About to write any query code
**Reality**: Assuming column names leads to wasted tool calls and KeyErrors
**Correct approach**: Run `df.columns.tolist()` as your FIRST action before writing ANY analysis code

```python
# FIRST - always check columns
print(df.columns.tolist())
# Output: ['Fiscal Year', 'Fiscal Quarter', 'Fiscal Period', 'FSLine Statement L1',
#          'FSLine Statement L2', 'Product', 'Country', 'Currency',
#          'Amount in Local Currency', 'Amount in USD', 'Version']

# THEN write your query using actual column names
```

### No Abbreviated Column Names (L2, Amount, etc.)
**Trigger**: Code uses `df['L2']`, `df['L1']`, or `df['Amount']`
**Reality**: The dataset uses full, descriptive column names - NOT abbreviations
**Correct approach**: Always use full column names:
- `df['FSLine Statement L2']` not `df['L2']`
- `df['FSLine Statement L1']` not `df['L1']`
- `df['Amount in USD']` not `df['Amount']`
- If unsure, run `df.columns.tolist()` first

### No Generic Column Names (Line Item, Year, Value)
**Trigger**: Code uses generic names like `df['Line Item']`, `df['Year']`, `df['Value']`
**Reality**: This dataset uses descriptive column names with spaces, not generic names
**Correct approach**:
- `df['FSLine Statement L2']` not `df['Line Item']`
- `df['Fiscal Year']` not `df['Year']`
- `df['Amount in USD']` not `df['Value']` or `df['Amount']`

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

### No Employee/HR Data - This is a Financial Dataset Only
**Trigger**: Query asks about employee headcount, salaries, FTEs, hiring, HR metrics, or workforce data
**Reality**: This is a P&L (Profit & Loss) financial dataset. It contains:
- Revenue, COGS, OPEX, Other Income/Expenses
- Amounts by Product, Country, Fiscal Period
It does NOT contain:
- Employee headcount or FTE counts
- Individual salaries or compensation data
- HR/workforce metrics
- Hiring or termination data

**Response**: Immediately explain that the requested data is not in this dataset. Do NOT attempt to search for non-existent columns.

```python
# WRONG - wasting tool calls searching for data that doesn't exist
if 'Employee Headcount' in df.columns:
    headcount = df['Employee Headcount'].sum()
# Then checking columns to "verify"...

# CORRECT - know upfront what data exists
# The dataset only has financial P&L data. For employee metrics,
# the user needs a separate HR/workforce dataset.
print("This dataset contains P&L financial data only (Revenue, COGS, OPEX, Other Income/Expenses).")
print("Employee headcount and HR metrics are not available in this dataset.")
```

**Note**: While there is a `Headcount Expenses` L2 line item under OPEX, this represents the dollar cost, NOT the number of employees.

### Pandas Pivot Table Column Suffixes After Merge
**Trigger**: Merging two pivot tables that share column names
**Reality**: Pandas automatically adds `_x` and `_y` suffixes to disambiguate overlapping columns
**Response**: Either use `suffixes=('_name1', '_name2')` in merge, or check `merged.columns.tolist()` after merge

```python
# After pivoting and merging:
revenue_pivot = df.pivot_table(index=['Country'], columns='Product', values='Revenue')
cogs_pivot = df.pivot_table(index=['Country'], columns='Product', values='COGS')
merged = revenue_pivot.merge(cogs_pivot, on=['Country'])

# WRONG - these column names don't exist after merge!
merged['Product A']  # KeyError!

# CORRECT - check actual columns after merge
print(merged.columns.tolist())
# Shows: ['Country', 'Product A_x', 'Product A_y', 'Product B_x', ...]
# Where _x is revenue, _y is cogs
```

### Version Column Value is 'Actuals' Not 'Actual'
**Trigger**: Filtering the dataset by version
**Reality**: The Version column value is `'Actuals'` (with an 's'), not `'Actual'`
**Response**: Always use `df[df['Version'] == 'Actuals']`

```python
# WRONG - returns empty DataFrame!
df_actuals = df[df['Version'] == 'Actual']  # No 's' - returns 0 rows silently

# CORRECT - include the 's'
df_actuals = df[df['Version'] == 'Actuals']
```

### Pandas GroupBy.apply() Index/Column Ambiguity
**Trigger**: Using groupby().apply() that modifies the DataFrame, then trying to groupby on the same column again
**Reality**: After apply(), the grouping columns may become both index levels AND column labels, causing ambiguity errors
**Response**: Use a manual loop approach instead, or reset_index() after each groupby operation

```python
# WRONG - causes "ValueError: 'column_name' is both an index level and a column label"
def add_variance(group):
    group['Variance'] = group['Amount'] - group['Amount'].mean()
    return group

result = df.groupby(['Product', 'Period']).apply(add_variance)
summary = result.groupby('Product')['Variance'].mean()  # ERROR!

# CORRECT - use manual loop to avoid ambiguity
results = []
for (product, period), group in df.groupby(['Product', 'Period']):
    variance = group['Amount'].values[0] - df[df['Product'] == product]['Amount'].mean()
    results.append({'Product': product, 'Period': period, 'Variance': variance})
variance_df = pd.DataFrame(results)
```
