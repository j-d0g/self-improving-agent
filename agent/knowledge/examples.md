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

### MISTAKE: Providing Fabricated Results Without Execution

**Query**: "What's the revenue for Q4?"

**Wrong approach**:
```python
# Thinking about what code would look like...
# Then providing an answer like "Q4 Revenue: $54,900,000.00" without running anything
```

**Why it fails**: The learner claimed a specific numeric result ($54,900,000.00) without actually executing any code. The "thinking" mentioned using `df['Quarter']` and `df['Revenue']` - columns that don't exist - but no tool call was made to run the analysis. The only tool call was to write a reflection log, not to compute results.

This is WORSE than providing untested code because:
1. The user receives a confident-sounding but potentially incorrect answer
2. The column names in the thinking (`Quarter`, `Revenue`) were wrong
3. No way to verify the number is correct

**Correct approach**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# CRITICAL: Use 'Fiscal Quarter' NOT 'Quarter', and filter by L1 for revenue
q4_revenue = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()

print('Q4 Revenue: ${:,.2f}'.format(q4_revenue))
```

**How to recognize this trap**: If you're about to give a specific number as an answer, verify that you made a Bash tool call that executed Python code and produced that number. Reflection logs don't count!

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

### MISTAKE: Using 'Quarter' Instead of 'Fiscal Quarter'

**Query**: "What's the revenue for Q4?" or any quarterly analysis

**Wrong approach**:
```python
# WRONG - there is no 'Quarter' column!
df[df['Quarter'] == 'Q4']  # KeyError: 'Quarter'
quarterly_revenue = df.groupby('Quarter')['Revenue'].sum()  # Multiple errors!
```

**Why it fails**: The column is named `Fiscal Quarter`, not `Quarter`. Additionally, there is no `Revenue` column - you must filter by `FSLine Statement L1 == 'Net Revenue'` and sum `Amount in USD`.

**Correct approach**:
```python
# CORRECT - use 'Fiscal Quarter' and filter by L1 for revenue
q4_revenue = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()
```

**How to recognize this trap**: Any time you need quarterly data, use `Fiscal Quarter`. Any time you need revenue, filter `FSLine Statement L1 == 'Net Revenue'` and aggregate `Amount in USD`.

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

### MISTAKE: Using 'Revenue' Instead of 'Gross Revenue' for L2 Filtering

**Query**: Any query about revenue that filters by FSLine Statement L2

**Wrong approach**:
```python
# WRONG - there is no L2 value called 'Revenue'!
revenue_df = df[df['FSLine Statement L2'] == 'Revenue']  # Returns empty DataFrame!
```

**Why it fails**: At the L2 level, the revenue line item is named `'Gross Revenue'`, not `'Revenue'`. The word 'Revenue' appears in the L1 value (`'Net Revenue'`), but at L2 it's more specific. Filtering L2 for 'Revenue' returns 0 rows.

**Correct approaches**:
```python
# CORRECT Option 1 (PREFERRED for total revenue) - Use L1 filtering
revenue_df = df[df['FSLine Statement L1'] == 'Net Revenue']

# CORRECT Option 2 (for granular L2 analysis) - Use 'Gross Revenue'
gross_revenue_df = df[df['FSLine Statement L2'] == 'Gross Revenue']

# CORRECT Option 3 (for all revenue components at L2)
revenue_df = df[df['FSLine Statement L2'].isin(['Gross Revenue', 'Returns and Refunds', 'Revenue Adjustment'])]
```

**How to recognize this trap**: If your revenue filter returns 0 rows or an empty DataFrame:
1. Check if you're using L2 with 'Revenue' - it should be 'Gross Revenue'
2. Consider using L1 with 'Net Revenue' instead for total revenue
3. Verify L2 values with: `print(df['FSLine Statement L2'].unique())`

**L2 Revenue Components**:
- `'Gross Revenue'` - Main revenue line item
- `'Returns and Refunds'` - Deductions from revenue
- `'Revenue Adjustment'` - Other revenue adjustments

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

### Variance Analysis with Manual Loop (Avoiding GroupBy Ambiguity)

**Query**: "Perform a variance analysis comparing each month's actuals against the yearly average for all L2 line items"

**Interpretation**: For each L2 line item, calculate how each fiscal period deviates from the L2's overall yearly average, expressed as a percentage variance.

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# CRITICAL: Use 'Actuals' (with 's'), not 'Actual'
df_actuals = df[df['Version'] == 'Actuals']

# Get unique L2 items and fiscal periods
l2_items = df_actuals['FSLine Statement L2'].unique()
fiscal_periods = df_actuals['Fiscal Period'].unique()

# Compute yearly average for each L2 item
yearly_averages = df_actuals.groupby('FSLine Statement L2')['Amount in USD'].mean()

# Use manual loop to avoid pandas groupby.apply() ambiguity
results = []
for l2_item in l2_items:
    item_data = df_actuals[df_actuals['FSLine Statement L2'] == l2_item]
    yearly_avg = yearly_averages[l2_item]

    for period in fiscal_periods:
        period_data = item_data[item_data['Fiscal Period'] == period]
        if not period_data.empty:
            period_amount = period_data['Amount in USD'].values[0]
            variance_pct = ((period_amount - yearly_avg) / yearly_avg * 100)
            results.append({
                'FSLine Statement L2': l2_item,
                'Fiscal Period': period,
                'Amount in USD': period_amount,
                'Yearly Average': yearly_avg,
                'Variance Percentage': variance_pct
            })

# Convert to DataFrame for analysis
variance_df = pd.DataFrame(results)

# Now compute summary stats - this works because we built a fresh DataFrame
summary = variance_df.groupby('FSLine Statement L2')['Variance Percentage'].agg([
    'count', 'mean', 'min', 'max', 'std'
]).sort_values('std', ascending=False)

print('Variance Analysis Summary by L2 Line Item:')
print(summary)
```

**Key insight**:
1. **CRITICAL**: Use `'Actuals'` (with 's') not `'Actual'` for Version filtering - singular returns empty DataFrame
2. **CRITICAL**: Use `'FSLine Statement L2'` not `'L2'` - abbreviated column names don't exist
3. Use manual loop instead of `groupby().apply()` to avoid index/column ambiguity errors
4. Pre-compute yearly averages with a simple groupby before the loop
5. Build a fresh DataFrame from the results list - this avoids any index ambiguity issues
6. Variance formula: `(period_value - yearly_avg) / yearly_avg * 100`

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

---

## Positive Examples (continued)

### Finding Outliers in the Dataset

**Query**: "Find all outliers in the dataset"

**Interpretation**: Identify data points that are statistically unusual compared to the overall distribution, typically using Z-score or IQR methods.

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv("data/FUN_company_pl_actuals_dataset.csv")

# Aggregate by meaningful dimensions (L1, Product, Country, Year)
df_aggregated = df.groupby(
    ["FSLine Statement L1", "Product", "Country", "Fiscal Year"]
)["Amount in USD"].sum().reset_index()
df_aggregated.columns = ["L1", "Product", "Country", "Year", "Total_Amount"]

# Calculate Z-scores (number of standard deviations from mean)
df_aggregated["Z_Score"] = np.abs(
    (df_aggregated["Total_Amount"] - df_aggregated["Total_Amount"].mean())
    / df_aggregated["Total_Amount"].std()
)

# Find outliers (Z-score > 2 = more than 2 standard deviations from mean)
outliers_df = df_aggregated[df_aggregated["Z_Score"] > 2].sort_values("Total_Amount")

# Print results
print("Outliers in Financial Data:\n")
print(outliers_df[["L1", "Product", "Country", "Year", "Total_Amount", "Z_Score"]].to_string(index=False))

# Summary statistics
if not outliers_df.empty:
    print(f"\n\nTotal Outliers Found: {len(outliers_df)}")
    print(f"Minimum Outlier Amount: ${outliers_df.Total_Amount.min():,.2f}")
    print(f"Maximum Outlier Amount: ${outliers_df.Total_Amount.max():,.2f}")

    # Distribution by dimension
    print("\nOutlier Distribution by L1:")
    print(outliers_df["L1"].value_counts())
```

**Key insight**:
1. **CRITICAL**: Run this via single-quoted bash command: `python3 -c '...'` with double quotes inside
2. **CRITICAL**: The dataset does NOT have columns named 'Revenue' or 'COGS' - use `Amount in USD` for values
3. Aggregate first before outlier detection - raw rows are not meaningful for outlier analysis
4. Z-score method: values > 2 standard deviations from mean are outliers
5. Alternative: IQR method (Q1 - 1.5*IQR to Q3 + 1.5*IQR defines normal range)
6. Always check `df.columns.tolist()` BEFORE writing analysis code to avoid KeyErrors

---

### Finding Outliers Using IQR Method (Raw Values)

**Query**: "Find all outliers in the dataset"

**Interpretation**: Identify data points that fall outside the normal distribution using the Interquartile Range (IQR) method on raw numerical values.

**Code**:
```python
import pandas as pd
import numpy as np

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Identify numerical columns
numerical_columns = df.select_dtypes(include=['float64', 'int64']).columns

# Function to find outliers using IQR method
def find_outliers(series):
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return (series < lower_bound) | (series > upper_bound)

# Dictionary to store outliers
outliers = {}

# Find outliers for each numerical column
for col in numerical_columns:
    col_outliers = df[find_outliers(df[col])]
    if not col_outliers.empty:
        outliers[col] = col_outliers

# Print summary of outliers
print('Outliers Summary:')
for col, outlier_df in outliers.items():
    print(f'\nColumn: {col}')
    print(f'Number of outliers: {len(outlier_df)}')
    print(f'Outlier Percentage: {len(outlier_df) / len(df) * 100:.2f}%')
    print('\nSample of Outliers:')
    print(outlier_df.head())

# Optional: Save detailed outliers to CSV
if outliers:
    outlier_details = pd.concat(outliers.values())
    outlier_details.to_csv('logs/outliers_detailed.csv', index=False)
    print('\nDetailed outliers saved to logs/outliers_detailed.csv')
```

**Key insight**:
1. **IQR method**: Outliers are values < Q1 - 1.5*IQR or > Q3 + 1.5*IQR (Q1 = 25th percentile, Q3 = 75th percentile)
2. This approach works on **raw values** - useful when you want to find unusual individual records
3. Alternative: **Z-score method** (see "Finding Outliers in the Dataset" example above) - better for aggregated data
4. Both Amount columns (`Amount in Local Currency`, `Amount in USD`) typically show ~9-10% outliers in this dataset
5. Save results to CSV for further investigation when dealing with thousands of outliers

---

### MISTAKE: Confusion with Pandas Pivot Table Column Names After Merge

**Query**: Any query comparing multiple products side-by-side using pivot tables

**Wrong approach**:
```python
# After pivoting revenue and COGS separately and merging...
revenue_pivot = df.pivot_table(index=['Country'], columns='Product', values='Amount')
cogs_pivot = df.pivot_table(index=['Country'], columns='Product', values='COGS_Amount')

# Rename columns BEFORE merge
revenue_pivot = revenue_pivot.rename(columns=lambda x: f'Revenue_{x}' if x in ['A', 'B'] else x)

# WRONG - after merge, columns become 'Revenue_A_x' and 'Revenue_A_y' or similar!
merged = revenue_pivot.merge(cogs_pivot, on=['Country'])
merged['Gross_Margin_A'] = merged['Revenue_A'] - merged['COGS_A']  # KeyError!
```

**Why it fails**: When merging two DataFrames with overlapping column names, pandas automatically adds `_x` and `_y` suffixes. After a pivot, the product names become columns, so merging two pivots creates suffixed columns like `Product A_x`, `Product A_y`.

**Correct approach**:
```python
# Option 1: Use suffixes parameter to control naming
merged = revenue_pivot.merge(
    cogs_pivot,
    on=['Country', 'Fiscal Year', 'Fiscal Period'],
    suffixes=('_rev', '_cogs')
)
# Now access as: merged['Product A_rev'], merged['Product A_cogs']

# Option 2: Rename AFTER merge using the actual column names
print(merged.columns.tolist())  # See actual column names first!
# Then reference correctly: merged['Product A_x'], merged['Product A_y']

# Option 3: Don't pivot - reshape differently
# Keep data long, merge on all grouping columns, then calculate
metrics = revenue.merge(cogs, on=['Product', 'Country', 'Fiscal Year', 'Fiscal Period'])
metrics['Gross_Margin'] = metrics['Revenue'] - metrics['COGS']
# THEN pivot at the end if needed for comparison
```

**How to recognize this trap**: Any time you're merging pivot tables, check `merged.columns.tolist()` immediately after the merge to see the actual column names before trying to access them.

---

### Filtering by Even/Odd Years

**Query**: "Revenue of all even years"

**Interpretation**: Calculate total revenue for years that are divisible by 2 (2020, 2022, 2024 in this dataset).

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# CRITICAL: Column is 'Fiscal Year' NOT 'Year'!
# Even years: 2020, 2022, 2024 (years divisible by 2)
even_years_revenue = df[
    (df['Fiscal Year'] % 2 == 0) &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()

# Odd years: 2021, 2023
odd_years_revenue = df[
    (df['Fiscal Year'] % 2 == 1) &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()

print('Even Years Revenue: $' + str(round(even_years_revenue, 2)))
print('Odd Years Revenue: $' + str(round(odd_years_revenue, 2)))
```

**Key insight**:
1. **CRITICAL**: Use `Fiscal Year` NOT `Year` - there is no 'Year' column
2. Use modulo operator `% 2 == 0` for even years, `% 2 == 1` for odd years
3. Available years are 2020, 2021, 2022, 2023, 2024
4. Combine year filter with L1 filter using `&` (must use parentheses around each condition)
5. When outputting currency in bash, use string concatenation `'$' + str(value)` instead of f-strings with `$` to avoid bash variable interpretation

---

### Comparing Two Subsets (X vs Y Queries)

**Query**: "Revenue of all even years vs revenue of all vowels"

**Interpretation**: Calculate and compare two distinct revenue totals:
1. Revenue for even years (2020, 2022, 2024)
2. Revenue for products with vowels in their name (Product A - since A is the only vowel among A, B, C, D)

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# CRITICAL: Filter for Net Revenue first
revenue_df = df[df['FSLine Statement L1'] == 'Net Revenue']

# Subset 1: Even years (2020, 2022, 2024)
# CRITICAL: Column is 'Fiscal Year' NOT 'Year'!
even_years_revenue = revenue_df[revenue_df['Fiscal Year'] % 2 == 0]['Amount in USD'].sum()

# Subset 2: Products with vowels (only Product A has a vowel - A)
# Note: Product C's letter 'C' is a consonant, not a vowel
# CRITICAL: Products are 'Product A', 'Product B', etc. - NOT just 'A', 'B'!
vowel_products = ['Product A']
vowel_revenue = revenue_df[revenue_df['Product'].isin(vowel_products)]['Amount in USD'].sum()

print('Even Years Revenue: $' + str(round(even_years_revenue, 2)))
print('Vowel Products Revenue: $' + str(round(vowel_revenue, 2)))
```

**Key insight**:
1. For "X vs Y" queries, identify what each subset represents and calculate separately
2. **CRITICAL**: `Fiscal Year` not `Year`, `Net Revenue` not `Revenue`, `Product A` not `A`
3. Among products A, B, C, D - only A is a vowel (A, E, I, O, U are vowels)
4. Avoid f-strings with `$` in bash - use `'$' + str(value)` or `.format()` instead
5. Pre-filter to `Net Revenue` once, then apply different filters for each subset

---

### MISTAKE: Assuming Product Values Are Just Letters

**Query**: Any query filtering by product

**Wrong approach**:
```python
# WRONG - Product values include the word "Product"!
df[df['Product'] == 'A']                     # Returns empty!
df['Product'].isin(['A', 'B', 'C', 'D'])     # Returns all False!
revenue_pivot.rename(columns={'A': 'Revenue_A'})  # No 'A' column exists!
```

**Why it fails**: The Product column contains full names: `'Product A'`, `'Product B'`, `'Product C'`, `'Product D'` - not just the letters.

**Correct approach**:
```python
# CORRECT - use full product names
df[df['Product'] == 'Product A']
df['Product'].isin(['Product A', 'Product B'])

# When renaming after pivot
revenue_pivot.rename(columns={'Product A': 'Revenue_A', 'Product B': 'Revenue_B'})
```

**How to recognize this trap**: If a product filter returns 0 rows, check the actual values:
```python
print(df['Product'].unique())
# Output: ['Product A' 'Product B' 'Product C' 'Product D']
```

---

### MISTAKE: Assuming Column Names Without Checking

**Query**: Any analytical query on the dataset

**Wrong approach**:
```python
# WRONG - assuming column names exist without verifying
df['Revenue']           # KeyError!
df['COGS']              # KeyError!
df['OPEX']              # KeyError!
df['Other Income']      # KeyError!
```

**Why it fails**: These are CONCEPTUAL names, not actual column names. The dataset stores financial categories in `FSLine Statement L1` and values in `Amount in USD`.

**Correct approach**:
```python
# CORRECT - first check columns, then use actual names
print(df.columns.tolist())
# Output: ['Fiscal Year', 'Fiscal Quarter', 'Fiscal Period', 'FSLine Statement L1',
#          'FSLine Statement L2', 'Product', 'Country', 'Currency',
#          'Amount in Local Currency', 'Amount in USD', 'Version']

# Then filter by L1 category
revenue = df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD'].sum()
cogs = df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD'].sum()
opex = df[df['FSLine Statement L1'] == 'OPEX']['Amount in USD'].sum()
```

**How to recognize this trap**: If you're about to access a column that sounds like a financial metric (Revenue, COGS, Profit, etc.), STOP. This dataset uses a normalized format where all values are in `Amount in USD` and the metric type is in `FSLine Statement L1/L2`.

---

### MISTAKE: Using 'Actual' Instead of 'Actuals' for Version Filtering

**Query**: Any query that filters by version or actuals data

**Wrong approach**:
```python
# WRONG - 'Actual' (singular) returns ZERO rows!
df_actuals = df[df['Version'] == 'Actual']
print(df_actuals['FSLine Statement L2'].unique())  # Output: [] - empty!
```

**Why it fails**: The Version column contains `'Actuals'` (with an 's'), not `'Actual'`. This filter silently returns an empty DataFrame, causing all subsequent analysis to fail or return empty results.

**Correct approach**:
```python
# CORRECT - use 'Actuals' with the 's'
df_actuals = df[df['Version'] == 'Actuals']
```

**How to recognize this trap**: If your filtered data returns 0 rows or empty results unexpectedly, check the Version filter. The value is `'Actuals'` (plural). Verify with:
```python
print(df['Version'].unique())
# Output: ['Actuals']
```

---

### MISTAKE: Assuming Generic Column Names (Line Item, Year, Value)

**Query**: Any query on this dataset

**Wrong approach**:
```python
# WRONG - assuming generic column names that don't exist!
df[(df['Line Item'] == 'Headcount') & (df['Year'] == 2023)]['Value'].sum()
# KeyError: 'Line Item'
```

**Why it fails**: This dataset does NOT use generic column names. The actual columns are:
- `FSLine Statement L1` / `FSLine Statement L2` (not `Line Item`)
- `Fiscal Year` (not `Year`)
- `Amount in USD` / `Amount in Local Currency` (not `Value` or `Amount`)

**Correct approach**:
```python
# CORRECT - use actual column names from the dataset
df[(df['FSLine Statement L2'] == 'Headcount Expenses') & (df['Fiscal Year'] == 2023)]['Amount in USD'].sum()

# BETTER - check columns FIRST before writing any code
print(df.columns.tolist())
# ['Fiscal Year', 'Fiscal Quarter', 'Fiscal Period', 'FSLine Statement L1',
#  'FSLine Statement L2', 'Product', 'Country', 'Currency',
#  'Amount in Local Currency', 'Amount in USD', 'Version']
```

**How to recognize this trap**: If you're about to write code using simple, generic column names (Year, Month, Value, Amount, Item, Type), STOP and check `df.columns.tolist()` first. This dataset uses descriptive column names with spaces.

---

### MISTAKE: Not Checking Column Names Before Writing Code (Trial and Error Pattern)

**Query**: Any analytical query on the dataset

**Wrong approach**:
```python
# WRONG - jumping straight into code with assumed column names
# Attempt 1 - fails
df[df['Year'] % 2 == 0]['Revenue'].sum()  # KeyError: 'Year'

# Attempt 2 - check columns after failure
print(df.columns.tolist())  # Now see 'Fiscal Year' not 'Year'

# Attempt 3 - fix Year but still wrong
df[df['Fiscal Year'] % 2 == 0]['Revenue'].sum()  # KeyError: 'Revenue'

# Multiple tool calls wasted before getting it right...
```

**Why it fails**: Assuming column names without checking leads to a trial-and-error pattern that wastes multiple tool calls. The learner made 10 tool calls for what should have been 1-2.

**Correct approach**:
```python
# CORRECT - ALWAYS check columns FIRST, THEN write analysis code
print(df.columns.tolist())
# Output: ['Fiscal Year', 'Fiscal Quarter', 'Fiscal Period', 'FSLine Statement L1',
#          'FSLine Statement L2', 'Product', 'Country', 'Currency',
#          'Amount in Local Currency', 'Amount in USD', 'Version']

# Also check unique values for filter columns
print(df['FSLine Statement L1'].unique())
# Output: ['Cost of Goods Sold' 'Net Revenue' 'OPEX' 'Other Income/Expenses']

print(df['Product'].unique())
# Output: ['Product A' 'Product B' 'Product C' 'Product D']

# NOW write the correct query in one shot
revenue = df[(df['Fiscal Year'] % 2 == 0) &
             (df['FSLine Statement L1'] == 'Net Revenue')]['Amount in USD'].sum()
```

**How to recognize this trap**: If your first instinct is to start writing analysis code immediately, STOP. Always run these checks first:
1. `df.columns.tolist()` - see actual column names
2. `df['column'].unique()` - see valid values for filter columns
This turns a 10-tool-call session into a 2-tool-call session.

---

### MISTAKE: Not Using include_groups=False with GroupBy.apply()

**Query**: Any query using groupby().apply() to calculate YoY changes or rolling metrics

**Wrong approach**:
```python
# WRONG - triggers FutureWarning and may behave unexpectedly in future pandas versions
def calculate_yoy_change(group):
    group = group.sort_values('Fiscal Year')
    group['Margin_Change'] = group['Profit_Margin'] - group['Profit_Margin'].shift(1)
    return group

result = df.groupby(['Product', 'Country']).apply(calculate_yoy_change)  # Missing include_groups=False!
# FutureWarning: DataFrameGroupBy.apply operated on the grouping columns.
# This behavior is deprecated...
```

**Why it fails**: Starting in pandas 2.0+, `groupby().apply()` includes the grouping columns in the operation by default, but this behavior is deprecated. Without `include_groups=False`, you get a FutureWarning and the behavior may change in future versions.

**Correct approach**:
```python
# CORRECT - explicitly exclude grouping columns
result = df.groupby(['Product', 'Country'], group_keys=False).apply(
    calculate_yoy_change, include_groups=False
)
```

**How to recognize this trap**: Any time you use `groupby().apply()` with a function that modifies or returns the group, add `include_groups=False` to suppress the warning and ensure consistent behavior.

---

### MISTAKE: Filtering L2 with 'Operating Expenses' Which Doesn't Exist

**Query**: "Calculate OPEX for each product" or any query involving operating expenses

**Wrong approach**:
```python
# WRONG - 'Operating Expenses' does NOT exist as an L2 value!
opex_df = df[df['FSLine Statement L2'] == 'Operating Expenses']  # Returns empty DataFrame!
```

**Why it fails**: The FSLine Statement L2 column contains granular line items like 'General & Administrative', 'Marketing Expenses', etc. There is NO L2 value called 'Operating Expenses'. That terminology exists only at the conceptual level - the actual L1 value is `'OPEX'`.

**Correct approaches**:
```python
# CORRECT Option 1 (PREFERRED) - Use L1 filtering with 'OPEX'
opex_df = df[df['FSLine Statement L1'] == 'OPEX']

# CORRECT Option 2 - Use L2 with the actual component values
opex_items = [
    'General & Administrative', 'Headcount Expenses', 'IT Expenses',
    'Marketing Expenses', 'R&D Expenses', 'Sales Expenses'
]
opex_df = df[df['FSLine Statement L2'].isin(opex_items)]
```

**How to recognize this trap**: If your OPEX filter returns 0 rows, you probably used the wrong column or value:
- L1 uses: `'OPEX'` (not 'Operating Expenses')
- L2 uses: Individual expense categories (not 'Operating Expenses')

Print unique values to verify: `print(df['FSLine Statement L2'].unique())`

---

### MISTAKE: Assuming Helper Functions Exist in functions.py

**Query**: Any query where you try to use helper functions from knowledge/functions.py

**Wrong approach**:
```python
# WRONG - assuming functions exist without checking!
import sys
sys.path.insert(0, 'knowledge')
from functions import safe_read_csv  # ImportError! This function doesn't exist

df = safe_read_csv('data/FUN_company_pl_actuals_dataset.csv')
```

**Why it fails**: The learner assumed a `safe_read_csv` helper function exists in `knowledge/functions.py`, but it doesn't. This wastes a tool call and requires recovery.

**Correct approach**:
```python
# CORRECT - use standard pandas, or check functions.py first
import pandas as pd
df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# If you want to use helper functions, check what's actually available:
# 1. calculate_rolling_average_with_threshold
# 2. compare_products_on_metrics
# 3. find_outliers_iqr
# 4. find_outliers_zscore
```

**How to recognize this trap**: Before importing from `knowledge/functions.py`, either:
1. Use standard pandas (it's always available and reliable)
2. Check what functions actually exist in the file first

The helper functions in `functions.py` are for specific complex patterns (rolling averages, product comparisons, outlier detection) - not basic operations like reading CSV files.

---

### MISTAKE: Pandas GroupBy.apply() Creating Index/Column Ambiguity

**Query**: Any variance analysis or transformation that uses groupby().apply() followed by another groupby

**Wrong approach**:
```python
# WRONG - after apply(), subsequent groupby fails with ambiguity error
def compute_variance(group):
    yearly_avg = group['Amount in USD'].mean()
    group['Variance'] = group['Amount in USD'] - yearly_avg
    return group

# First groupby works...
result = df.groupby(['FSLine Statement L2', 'Fiscal Period']).apply(compute_variance)

# But this fails!
summary = result.groupby('FSLine Statement L2')['Variance'].agg(['mean', 'std'])
# ValueError: 'FSLine Statement L2' is both an index level and a column label
```

**Why it fails**: When using `groupby().apply()`, pandas may keep the grouping columns as both index levels AND column labels. Subsequent groupby operations become ambiguous because pandas doesn't know which to use.

**Correct approach**:
```python
# CORRECT - use manual loop to avoid ambiguity entirely
l2_items = df['FSLine Statement L2'].unique()
fiscal_periods = df['Fiscal Period'].unique()

results = []
for l2_item in l2_items:
    item_data = df[df['FSLine Statement L2'] == l2_item]
    yearly_avg = item_data['Amount in USD'].mean()

    for period in fiscal_periods:
        period_data = item_data[item_data['Fiscal Period'] == period]
        if not period_data.empty:
            period_amount = period_data['Amount in USD'].values[0]
            variance_pct = ((period_amount - yearly_avg) / yearly_avg * 100)
            results.append({
                'FSLine Statement L2': l2_item,
                'Fiscal Period': period,
                'Variance Percentage': variance_pct
            })

variance_df = pd.DataFrame(results)
# Now you can safely groupby on variance_df
summary = variance_df.groupby('FSLine Statement L2')['Variance Percentage'].agg(['mean', 'std'])
```

**How to recognize this trap**: If you get a `ValueError: 'X' is both an index level and a column label` after using groupby().apply(), switch to a manual loop approach. This is especially common in variance analysis patterns.

---

## Positive Examples (continued)

### Quarterly Revenue Calculation

**Query**: "What's the revenue for Q4?"

**Interpretation**: Calculate the total revenue for fiscal quarter Q4 across all years, products, and countries.

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# CRITICAL: Column is 'Fiscal Quarter' NOT 'Quarter'!
# CRITICAL: Filter by L1 'Net Revenue', then sum 'Amount in USD'
q4_revenue = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()

print('Q4 Revenue: ${:,.2f}'.format(q4_revenue))

# For breakdown by year:
q4_by_year = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
].groupby('Fiscal Year')['Amount in USD'].sum()
print('\nQ4 Revenue by Year:')
print(q4_by_year)
```

**Key insight**:
1. **CRITICAL**: Use `Fiscal Quarter` NOT `Quarter` - there is no 'Quarter' column
2. **CRITICAL**: There is NO 'Revenue' column - filter by `FSLine Statement L1 == 'Net Revenue'` and aggregate `Amount in USD`
3. Fiscal Quarter values are: 'Q1', 'Q2', 'Q3', 'Q4' (strings, not integers)
4. Always EXECUTE the code - don't just write it in thinking and provide a fabricated answer!
5. When outputting currency in bash, use `.format()` instead of f-strings with `$` to avoid bash variable interpretation

---

### MISTAKE: Summing All Amounts Without Filtering by L1 Category

**Query**: "What was the revenue for Q4?"

**Wrong approach**:
```python
# WRONG - sums ALL financial categories, not just revenue!
q4_revenue = df[df['Fiscal Quarter'] == 'Q4']['Amount in USD'].sum()
print(f'{q4_revenue:,.0f}')  # Returns ~215,005,308 - but this includes COGS, OPEX, etc.!
```

**Why it fails**: The `Amount in USD` column contains values for ALL financial categories (Net Revenue, Cost of Goods Sold, OPEX, Other Income/Expenses). Without filtering by `FSLine Statement L1`, you're summing everything together - not just revenue. The result is meaningless and much larger than actual revenue.

**Correct approach**:
```python
# CORRECT - filter for Net Revenue FIRST, then sum
q4_revenue = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()
```

**How to recognize this trap**: Whenever you need a specific financial metric (revenue, COGS, OPEX), you MUST filter by `FSLine Statement L1` before summing `Amount in USD`. This dataset stores all financial categories in the same column with the category type in a separate column.

**Remember**:
- For revenue: `df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD']`
- For COGS: `df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD']`
- For OPEX: `df[df['FSLine Statement L1'] == 'OPEX']['Amount in USD']`

---

### Handling Queries for Non-Existent Data Types (Forecasts, Budgets)

**Query**: "What is the revenue forecasted for Q4?"

**Interpretation**: The user is asking for forecast/projected revenue data.

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Step 1: Check what versions exist in the dataset
print("Available versions:", df['Version'].unique())
# Output: ['Actuals'] - ONLY historical actuals, no forecasts

# Step 2: Provide helpful response since forecast data doesn't exist
print("\nThis dataset contains ONLY 'Actuals' (historical data).")
print("Forecast, budget, or projected data is not available.")
print("\nAlternatives:")
print("1. Request a separate forecast/budget dataset")
print("2. Build a forecasting model based on historical trends")
print("3. View actual Q4 revenue instead")

# Optional: Show actual Q4 data as a helpful alternative
actual_q4 = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
]['Amount in USD'].sum()
print('\nActual Q4 Revenue (historical): ${:,.2f}'.format(actual_q4))
```

**Key insight**:
1. **CRITICAL**: Check the `Version` column first - this dataset ONLY has `'Actuals'`
2. **Don't search endlessly**: If the user asks for forecasts/budgets/projections, check `Version` once and explain the limitation
3. **Be helpful**: Offer to show actual data as an alternative, or suggest how to obtain forecast data
4. **Key terms to watch for**: forecast, budget, projected, predicted, plan, target, estimate
5. This pattern applies to ANY query asking for data types that don't exist (not just forecasts)

---

### Simple Time-Series Forecasting (Average Method)

**Query**: "Forecast Q4 revenue" or "I'd like you to forecast it"

**Interpretation**: Create a forecast for a specific metric using historical data. Since this dataset only contains Actuals (no forecast data), we must build a simple forecasting model from historical trends.

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Step 1: Get historical Q4 revenue by year
# CRITICAL: Filter by L1 'Net Revenue' - don't sum all amounts!
q4_revenue = df[
    (df['Fiscal Quarter'] == 'Q4') &
    (df['FSLine Statement L1'] == 'Net Revenue')
].groupby('Fiscal Year')['Amount in USD'].sum()

print('Historical Q4 Revenue:')
print(q4_revenue)

# Step 2: Calculate simple average forecast
avg_forecast = q4_revenue.mean()
print('Average Q4 Revenue:', avg_forecast)

# Step 3: Calculate trend-based forecast (optional - requires sklearn)
# Note: Linear regression for better trend extrapolation
from sklearn.linear_model import LinearRegression
import numpy as np

X = q4_revenue.index.values.reshape(-1, 1)
y = q4_revenue.values
model = LinearRegression().fit(X, y)

# Predict next year
next_year = q4_revenue.index.max() + 1
trend_forecast = model.predict([[next_year]])[0]
print('Trend-based forecast for', next_year, ':', trend_forecast)
```

**Key insight**:
1. **CRITICAL**: When running in bash with `python3 -c "..."`, avoid f-strings with `${value:,.0f}` - bash interprets `$` as a variable!
   - Use `.format()` or simple prints instead
   - Or wrap the entire command in single quotes: `python3 -c '...'`
2. **CRITICAL**: Filter by `FSLine Statement L1 == 'Net Revenue'` before summing - don't sum all `Amount in USD` values!
3. Simple average is baseline; linear regression captures growth trends
4. Always show historical data alongside forecasts so user understands the basis
5. This dataset only has 'Actuals' - there's no built-in forecast data to retrieve

---

### MISTAKE: Repeated F-String Formatting Failures in Bash (Trial and Error Pattern)

**Query**: Any query involving formatted output with currency

**Wrong approach**:
```bash
# Attempt 1 - fails
python3 -c "
total = 1000
print(f'Total: ${total:,.0f}')  # bash interprets ${total...}
"
# Error: bad math expression: operand expected at ',.0f'

# Attempt 2 - still fails
python3 -c "
print(f'{value:,.0f}')  # bash interprets the braces
"
# Same error

# Repeated attempts (7+ times) before giving up on formatting...
```

**Why it fails**: The learner kept trying variations of f-strings with format specifiers inside bash double quotes, not recognizing that ALL of these will fail because bash interprets `$` and `{...}` before Python sees them.

**Correct approach**:
```bash
# BEST - use single quotes for bash, then f-strings work normally
python3 -c '
total = 1000
print(f"Total: ${total:,.2f}")  # Works! Single quotes block bash interpretation
'

# Alternative 1 - use .format() method
python3 -c "
total = 1000
print('Total: \${:,.2f}'.format(total))  # Escape the $ or use .format()
"

# Alternative 2 - skip currency formatting entirely for quick output
python3 -c "
total = 1000
print('Total:', total)  # Simple, always works
"
```

**How to recognize this trap**: If your FIRST attempt at formatted output fails with "bad math expression" or similar bash errors:
1. STOP trying variations of the same f-string approach
2. Switch to single-quoted bash command (`python3 -c '...'`)
3. Or remove the formatting entirely for the first pass, add formatting later if needed

**Root cause**: This is a bash vs Python quoting issue, not a Python issue. The solution is always to change how you invoke Python, not to modify the Python code repeatedly.

---

### Filtering Products by Character Pattern (Vowels, Consonants, etc.)

**Query**: "Revenue of all products that are vowels"

**Interpretation**: Find total revenue for products whose letter identifier (A, B, C, D) is a vowel. In this dataset, only Product A qualifies since A is the only vowel among A, B, C, D.

**Code**:
```python
import pandas as pd

df = pd.read_csv('data/FUN_company_pl_actuals_dataset.csv')

# Products in dataset: 'Product A', 'Product B', 'Product C', 'Product D'
# Vowels among A, B, C, D: only A
# CRITICAL: Product values include "Product " prefix!
vowel_products = ['Product A']

# For total revenue, use L1 filtering (Net Revenue includes all revenue components)
revenue = df[(df['Product'].isin(vowel_products)) &
             (df['FSLine Statement L1'] == 'Net Revenue')]['Amount in USD'].sum()

print('Total Revenue for Vowel Products: ${:,.2f}'.format(revenue))
```

**Key insight**:
1. **CRITICAL**: Products are named 'Product A', 'Product B', etc. - NOT just 'A', 'B', 'C', 'D'
2. **CRITICAL**: For revenue, use `FSLine Statement L1 == 'Net Revenue'` (preferred) or `FSLine Statement L2 == 'Gross Revenue'`
3. **CRITICAL**: There is NO column named 'Revenue' - values are in `Amount in USD`
4. When running in bash, avoid `$` in f-strings - use `.format()` instead: `'${:,.2f}'.format(value)`
5. Among the 4 products (A, B, C, D), only A is a vowel. If user asks for consonants, it would be Product B, C, D.

---
