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

**Best approach - Use single quotes for bash, double quotes for Python**:
```bash
# BEST - wrap the entire command in single quotes, use double quotes inside Python
python3 -c '
import pandas as pd
total = 1000.50
print(f"Total: ${total:,.2f}")  # Works! Bash ignores $ inside single quotes
'
```

This is the cleanest solution because:
1. Single quotes prevent bash from interpreting ANY special characters
2. You can use f-strings normally inside Python
3. You must use double quotes for Python strings (not single quotes inside single-quoted bash)

---

### MISTAKE: Using Abbreviated Column Names

**Query**: Any query involving L2 line items or Amount columns

**Wrong approach**:
```python
# WRONG - these abbreviated column names don't exist!
df['L2'].unique()          # KeyError: 'L2'
df['L1'].unique()          # KeyError: 'L1'
df['Amount']               # KeyError: 'Amount'
```

**Why it fails**: The dataset uses full, descriptive column names with spaces, not abbreviations. There is no `L2` column - it's `FSLine Statement L2`.

**Correct approach**:
```python
# CORRECT - use full column names exactly as they appear
df['FSLine Statement L2'].unique()    # L2 line items
df['FSLine Statement L1'].unique()    # L1 categories
df['Amount in USD']                   # USD amounts
df['Amount in Local Currency']        # Local currency amounts
```

**How to recognize this trap**: If you get a KeyError, print `df.columns.tolist()` to see exact column names. The dataset columns all use Title Case with spaces.

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

---

### MISTAKE: Using 'Operating Expenses' Instead of 'OPEX' for L1 Filtering

**Query**: Any query involving operating expenses

**Wrong approach**:
```python
# WRONG - the L1 value is 'OPEX', not 'Operating Expenses'!
df[df['FSLine Statement L1'] == 'Operating Expenses']
```

**Why it fails**: The FSLine Statement L1 column uses the abbreviated value `'OPEX'`, not the full name "Operating Expenses". Filtering with "Operating Expenses" returns an empty DataFrame.

**Correct approach**:
```python
# CORRECT - use 'OPEX' exactly as it appears in the data
df[df['FSLine Statement L1'] == 'OPEX']
```

**How to recognize this trap**: When filtering returns 0 rows unexpectedly, print unique values:
```python
print(df['FSLine Statement L1'].unique())
# Output: ['Cost of Goods Sold' 'Net Revenue' 'OPEX' 'Other Income/Expenses']
```

---

### MISTAKE: Assuming a 'date' Column Exists

**Query**: Any query involving time series, seasonal patterns, or date-based analysis

**Wrong approach**:
```python
# WRONG - there is no 'date' column!
df['date'] = pd.to_datetime(df['date'])  # KeyError: 'date'
df['month'] = df['date'].dt.month
df['quarter'] = df['date'].dt.quarter
```

**Why it fails**: The dataset uses separate fiscal columns for time information, not a combined date column. Attempting to access `df['date']` raises a KeyError.

**Correct approach**:
```python
# CORRECT - use the existing fiscal columns
# Fiscal Year: 2020, 2021, 2022, 2023, 2024 (int)
# Fiscal Quarter: Q1, Q2, Q3, Q4 (string)
# Fiscal Period: 2020-01, 2020-02, ... (string)

# For quarterly analysis:
df.groupby(['Fiscal Year', 'Fiscal Quarter'])['Amount in USD'].sum()

# For monthly analysis:
df.groupby(['Fiscal Year', 'Fiscal Period'])['Amount in USD'].sum()
```

**How to recognize this trap**: Before writing time-based analysis, check columns with `df.columns.tolist()`. The dataset uses Fiscal Year/Quarter/Period, not a datetime column.

---

### MISTAKE: Using 'Revenue' Instead of 'Net Revenue' for L1 Filtering

**Query**: Any query involving revenue

**Wrong approach**:
```python
# WRONG - the L1 value is 'Net Revenue', not 'Revenue'!
revenue_df = df[df['FSLine Statement L1'] == 'Revenue']  # Returns empty DataFrame!
```

**Why it fails**: The FSLine Statement L1 column uses `'Net Revenue'`, not `'Revenue'`. Filtering with 'Revenue' returns an empty DataFrame silently.

**Correct approach**:
```python
# CORRECT - use 'Net Revenue' exactly
revenue_df = df[df['FSLine Statement L1'] == 'Net Revenue']
```

**How to recognize this trap**: If your revenue analysis returns 0 or empty results, check the exact L1 values:
```python
print(df['FSLine Statement L1'].unique())
# Output: ['Cost of Goods Sold' 'Net Revenue' 'OPEX' 'Other Income/Expenses']
```

---

### MISTAKE: Trying to Use matplotlib for Visualization

**Query**: Any query where you want to create charts or visualizations

**Wrong approach**:
```python
# WRONG - matplotlib is not installed!
import matplotlib.pyplot as plt  # ModuleNotFoundError!
plt.figure(figsize=(12, 6))
df.plot(kind='bar')
plt.savefig('output.png')
```

**Why it fails**: The execution environment does not have matplotlib installed. Import will fail with ModuleNotFoundError.

**Correct approach**:
```python
# CORRECT - use text-based output with pivot tables
pivot = df.pivot_table(
    index='Fiscal Quarter',
    columns='Product',
    values='Amount in USD',
    aggfunc='sum'
).round(2)
print(pivot)

# Or save data to CSV for later visualization
pivot.to_csv('output.csv')
```

**How to recognize this trap**: Avoid matplotlib entirely. Use pandas pivot tables, formatted print statements, or save data to CSV files for visualization outside the environment.

---

## Positive Examples (continued)

### Seasonal Pattern Analysis

**Query**: "What are the seasonal patterns in this data?"

**Interpretation**: Analyze revenue (or other metrics) across fiscal quarters and periods to identify recurring seasonal trends and variability.

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Filter for Net Revenue (NOT 'Revenue' - use 'Net Revenue')
revenue_df = df[df['FSLine Statement L1'] == 'Net Revenue']

# Seasonal Analysis: Average Quarterly Revenue by Product
quarterly_revenue = revenue_df.groupby(['Fiscal Year', 'Fiscal Quarter', 'Product'])['Amount in USD'].sum().reset_index()
quarterly_pivot = quarterly_revenue.pivot_table(
    index='Fiscal Quarter',
    columns='Product',
    values='Amount in USD',
    aggfunc='mean'
).round(2)

print('Average Quarterly Revenue by Product:\n')
print(quarterly_pivot)

# Seasonal Variability Analysis (Coefficient of Variation)
quarterly_cv = quarterly_revenue.groupby('Fiscal Quarter')['Amount in USD'].apply(
    lambda x: x.std() / x.mean() * 100
).round(2)
print('\nQuarterly Revenue Variability (CV%):\n')
print(quarterly_cv)
```

**Key insight**:
1. **CRITICAL**: The dataset has NO 'date' column - use `Fiscal Year`, `Fiscal Quarter`, `Fiscal Period` directly
2. **CRITICAL**: Use `'Net Revenue'` not `'Revenue'` for L1 filtering - 'Revenue' returns empty DataFrame
3. **CRITICAL**: matplotlib is NOT available - use text-based pivot table output
4. Use `pivot_table` with `aggfunc='mean'` to average across years for seasonal patterns
5. Coefficient of Variation (CV) = std/mean * 100 measures seasonal variability
6. Always inspect columns and unique L1 values before writing analysis code

---

### Variance Analysis Against Period Average

**Query**: "Perform a variance analysis comparing each month's actuals against the yearly average for all L2 line items"

**Interpretation**: For each L2 line item, calculate how each fiscal quarter (or period) deviates from the yearly average, both in absolute terms and as a percentage.

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Filter for Actuals version
df_actuals = df[df['Version'] == 'Actuals']

# Get unique L2 line items
l2_items = df_actuals['FSLine Statement L2'].unique()

# Prepare results storage
variance_results = []

# Perform variance analysis for each L2 line item
for l2_item in l2_items:
    # Filter data for this L2 line item
    l2_data = df_actuals[df_actuals['FSLine Statement L2'] == l2_item]

    # Calculate yearly average for this L2 line item
    yearly_avg = l2_data['Amount in USD'].mean()

    # Group by Fiscal Quarter and calculate variances
    quarterly_data = l2_data.groupby('Fiscal Quarter')['Amount in USD'].agg([
        ('Quarterly_Total', 'sum'),
        ('Quarterly_Mean', 'mean'),
        ('Variance_from_Yearly_Avg', lambda x: x.mean() - yearly_avg),
        ('Variance_Percentage', lambda x: ((x.mean() - yearly_avg) / yearly_avg) * 100 if yearly_avg != 0 else 0)
    ]).reset_index()

    # Add L2 line item to results
    quarterly_data['FSLine Statement L2'] = l2_item
    quarterly_data['Yearly_Average'] = yearly_avg

    variance_results.append(quarterly_data)

# Combine all results
final_results = pd.concat(variance_results)

# Sort the results for better readability
final_results_sorted = final_results.sort_values(['FSLine Statement L2', 'Fiscal Quarter'])
print(final_results_sorted.to_string(index=False))
```

**Key insight**:
1. **CRITICAL**: Use `'FSLine Statement L2'` not `'L2'` - the abbreviated name doesn't exist
2. **CRITICAL**: Use `'Amount in USD'` not `'Amount'`
3. Filter for `Version == 'Actuals'` if needed (though this dataset is all Actuals)
4. Calculate yearly average first, then compare each period to it
5. Variance percentage formula: `(period_mean - yearly_avg) / yearly_avg * 100`
6. Use `pd.concat()` to combine results from loop iterations
7. There are 16 L2 line items in total across the 4 L1 categories

---

### Rolling Average with Threshold Detection

**Query**: "Calculate the 3-month rolling average of OPEX for each product and identify when any exceeded its rolling average by more than 10%"

**Interpretation**:
1. Calculate a 3-period rolling average of Operating Expenses for each product
2. Compare each period's actual OPEX to its rolling average
3. Flag periods where OPEX exceeded the rolling average by >10%

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Filter for OPEX (use 'OPEX' not 'Operating Expenses'!)
opex_df = df[df['FSLine Statement L1'] == 'OPEX']

# Group by Product and Fiscal Period, sum the amounts
opex_grouped = opex_df.groupby(['Product', 'Fiscal Period'])['Amount in USD'].sum().reset_index()

# Sort by Product and Fiscal Period to ensure correct rolling calculation
opex_sorted = opex_grouped.sort_values(['Product', 'Fiscal Period'])

# Calculate 3-period rolling average
opex_sorted['Rolling_Avg'] = opex_sorted.groupby('Product')['Amount in USD'].rolling(
    window=3, min_periods=1
).mean().reset_index(0, drop=True)

# Calculate the difference from rolling average
opex_sorted['Diff_From_Avg'] = opex_sorted['Amount in USD'] - opex_sorted['Rolling_Avg']
opex_sorted['Diff_Percentage'] = (opex_sorted['Diff_From_Avg'] / opex_sorted['Rolling_Avg']) * 100

# Identify instances where OPEX exceeded rolling average by more than 10%
exceeded = opex_sorted[opex_sorted['Diff_Percentage'] > 10]

print(exceeded[['Product', 'Fiscal Period', 'Amount in USD', 'Rolling_Avg', 'Diff_Percentage']])
```

**Key insight**:
1. **CRITICAL**: Use `'OPEX'` not `'Operating Expenses'` for FSLine Statement L1 filtering
2. Sort by Product and Fiscal Period BEFORE applying rolling window
3. Use `min_periods=1` to include early periods with less than 3 data points
4. The `reset_index(0, drop=True)` after rolling is needed to align the rolling result back to the original DataFrame
5. Percentage calculation: `(actual - rolling_avg) / rolling_avg * 100`

---

### MISTAKE: Searching for Data That Doesn't Exist in This Dataset

**Query**: "What was the employee headcount in 2023?"

**Wrong approach**:
```python
# WRONG - wasting tool calls searching for non-existent data
if 'Employee Headcount' in df.columns:
    headcount = df['Employee Headcount'].sum()
else:
    print('Column not found')  # Then checking df.columns to "verify"...
```

**Why it fails**: This P&L dataset only contains financial data (Revenue, COGS, OPEX, Other Income/Expenses). It does NOT contain:
- Employee headcount or FTE counts
- Individual salaries or compensation data
- HR/workforce metrics
- Hiring or termination data

**Correct approach**:
```python
# CORRECT - know upfront what data exists and respond immediately
# This is a financial P&L dataset. It contains:
# - FSLine Statement L1: Net Revenue, Cost of Goods Sold, OPEX, Other Income/Expenses
# - FSLine Statement L2: Detailed line items (Gross Revenue, Direct Labor, etc.)
# - Dimensions: Product (A,B,C,D), Country, Fiscal Year/Quarter/Period
# - Values: Amount in USD, Amount in Local Currency

# For employee/HR data, the user needs a separate dataset.
print("This dataset contains P&L financial data only.")
print("Employee headcount is not available. You would need HR/workforce data for that.")
```

**How to recognize this trap**: Before writing code, verify the query matches the dataset scope:
- P&L data: Revenue, COGS, OPEX, Other Income ✓
- HR data: Headcount, salaries, hiring ✗
- Operational data: Units sold, inventory ✗

**Note**: `Headcount Expenses` is an L2 line item (dollar cost of employees), but it's NOT employee count data.
