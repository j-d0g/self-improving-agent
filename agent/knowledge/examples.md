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

---

## Positive Examples (continued)

### Profit Margin with Year-over-Year Comparison

**Query**: "For each product-country-year combination, calculate the profit margin and flag any that changed by more than 5 percentage points from the previous year"

**Interpretation**:
1. Calculate profit margin (Profit / Revenue × 100) for each product-country-year
2. Compare each year to the previous year for the same product-country
3. Flag combinations where the change exceeds ±5 percentage points

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Get Revenue, COGS, and OPEX for each product-country-year
revenue_df = df[df['FSLine Statement L1'] == 'Net Revenue'].groupby(
    ['Product', 'Country', 'Fiscal Year']
)['Amount in USD'].sum().reset_index(name='Revenue')

cogs_df = df[df['FSLine Statement L1'] == 'Cost of Goods Sold'].groupby(
    ['Product', 'Country', 'Fiscal Year']
)['Amount in USD'].sum().reset_index(name='COGS')

opex_df = df[df['FSLine Statement L1'] == 'OPEX'].groupby(
    ['Product', 'Country', 'Fiscal Year']
)['Amount in USD'].sum().reset_index(name='OPEX')

# Merge all components
merged = revenue_df.merge(cogs_df, on=['Product', 'Country', 'Fiscal Year'], how='outer')
merged = merged.merge(opex_df, on=['Product', 'Country', 'Fiscal Year'], how='outer')
merged = merged.fillna(0)

# Calculate Profit and Profit Margin
merged['Profit'] = merged['Revenue'] - merged['COGS'] - merged['OPEX']
merged['Profit_Margin'] = np.where(
    merged['Revenue'] != 0,
    merged['Profit'] / merged['Revenue'] * 100,
    0
)

# Sort for YoY calculation
merged = merged.sort_values(['Product', 'Country', 'Fiscal Year'])

# Calculate YoY changes within each product-country group
def calculate_yoy_change(group):
    group = group.sort_values('Fiscal Year')
    group['Prev_Profit_Margin'] = group['Profit_Margin'].shift(1)
    group['Margin_Change'] = group['Profit_Margin'] - group['Prev_Profit_Margin']
    group['Significant_Change'] = group['Margin_Change'].abs() > 5
    return group

# Apply to each group (use include_groups=False to avoid FutureWarning)
result = merged.groupby(['Product', 'Country'], group_keys=False).apply(
    calculate_yoy_change, include_groups=False
)

# Filter for significant changes (exclude first year which has no previous)
significant = result[result['Significant_Change'] & result['Prev_Profit_Margin'].notna()]

print(significant[['Product', 'Country', 'Fiscal Year', 'Profit_Margin', 'Prev_Profit_Margin', 'Margin_Change']])
```

**Key insight**:
1. Build financial metrics by aggregating from L1 categories separately, then merge
2. Use `groupby().apply()` with a helper function for YoY calculations
3. Include `include_groups=False` in newer pandas versions to avoid deprecation warnings
4. When flagging changes, exclude the first year (no previous year to compare)
5. Always use `fillna(0)` after outer merges to handle missing combinations

---

### MISTAKE: Assuming L2 Values Match L1 Names

**Query**: Any query filtering by FSLine Statement L2

**Wrong approach**:
```python
# WRONG - 'Revenue' and 'Cost of Goods Sold' are L1 values, not L2!
df[df['FSLine Statement L2'] == 'Revenue']
df[df['FSLine Statement L2'] == 'Cost of Goods Sold']
```

**Why it fails**: L2 values are more granular (e.g., 'Gross Revenue', 'Direct Labor'). The L1 category names do not appear in L2.

**Correct approach**:
```python
# CORRECT - use actual L2 values
revenue = df[df['FSLine Statement L2'].isin(['Gross Revenue', 'Revenue Adjustment'])]['Amount in USD'].sum()
cogs = df[df['FSLine Statement L2'].isin(['Direct Labor', 'Direct Materials', 'Manufacturing Overhead'])]['Amount in USD'].sum()
```

**How to recognize this trap**: When you need granular line items (L2), look up the actual L2 values in schema.md. When you just need category totals, use L1 filtering instead.

---

### MISTAKE: Using Dollar Signs in Python F-Strings Inside Bash Commands

**Query**: Any query where you format output with currency symbols

**Wrong approach**:
```bash
python3 -c "
total = 1000.50
print(f'Total: ${total:,.2f}')  # WRONG - bash interprets $total as a variable
"
```

**Why it fails**: When running Python via `python3 -c "..."` in bash, the `$` symbol inside the Python f-string is interpreted by bash as a shell variable reference, not as a literal dollar sign. This causes errors like `bad math expression` or `command not found`.

**Correct approaches**:
```python
# Option 1: Use % formatting instead
print('Total: $%0.2f' % total)

# Option 2: Use .format() with explicit dollar sign
print('Total: ${:.2f}'.format(total))

# Option 3: Concatenate the dollar sign separately
print('Total: $' + '{:.2f}'.format(total))
```

**How to recognize this trap**: Any time you're using `$` in output formatting inside a bash -c command with Python, the dollar sign will be interpreted by bash. Use alternative formatting methods.

---

### MISTAKE: Case-Sensitive Column Names

**Query**: Any query accessing DataFrame columns

**Wrong approach**:
```python
# WRONG - column names are case-sensitive!
df['country']      # KeyError!
df['fiscal year']  # KeyError!
df['product']      # KeyError!
```

**Why it fails**: Pandas DataFrame column names are case-sensitive. The dataset uses Title Case column names.

**Correct approach**:
```python
# CORRECT - use exact case as in the dataset
df['Country']
df['Fiscal Year']
df['Product']
```

**How to recognize this trap**: If you get a KeyError for a column that "should" exist, check the case. Print `df.columns.tolist()` to see exact column names.

---

### MISTAKE: Calculating FX Impact from Currency Difference

**Query**: "Analyze the foreign exchange impact"

**Wrong approach**:
```python
# WRONG - you can't subtract amounts in different currencies!
df['FX_Variance'] = np.abs(df['Amount in USD'] - df['Amount in Local Currency'])
```

**Why it fails**: `Amount in Local Currency` and `Amount in USD` are in different units. Subtracting JPY from USD doesn't give you meaningful FX impact - the numbers are orders of magnitude different (1 USD ≈ 150 JPY).

**Correct approach**:
```python
# CORRECT - use the explicit Foreign Exchange Gain/Loss line item
fx_impact = df[df['FSLine Statement L2'] == 'Foreign Exchange Gain/Loss'].groupby(
    ['Country', 'Fiscal Year']
)['Amount in USD'].sum()
```

**How to recognize this trap**: The dataset already records FX gains/losses as a line item under "Other Income/Expenses". Use that instead of trying to calculate FX impact yourself.

---

## Positive Examples (continued)

### Foreign Exchange Impact Analysis

**Query**: "Analyze the foreign exchange impact"

**Interpretation**: Analyze the foreign exchange gains and losses recorded in the P&L data

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Get FX Gain/Loss from the dedicated line item
fx_data = df[df['FSLine Statement L2'] == 'Foreign Exchange Gain/Loss']

# Aggregate by Country and Year
fx_by_country_year = fx_data.groupby(['Country', 'Fiscal Year'])['Amount in USD'].sum().unstack()
print("FX Gain/Loss by Country and Year:")
print(fx_by_country_year)

# Total FX impact by country
fx_by_country = fx_data.groupby('Country')['Amount in USD'].agg(['sum', 'mean', 'count'])
print("\nTotal FX Impact by Country:")
print(fx_by_country)

# Year-over-year FX trend
fx_by_year = fx_data.groupby('Fiscal Year')['Amount in USD'].sum()
print("\nFX Gain/Loss by Year:")
print(fx_by_year)
```

**Key insight**:
1. Use the `Foreign Exchange Gain/Loss` line item from FSLine Statement L2
2. Positive values = FX gains, Negative values = FX losses
3. The Currency column shows each country's local currency (AUD, CAD, EUR, JPY, GBP, USD)
4. US has no FX impact since USD is the reporting currency
