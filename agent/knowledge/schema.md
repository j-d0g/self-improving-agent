# P&L Dataset Schema

This file documents the structure and valid values in the P&L dataset.

## Dataset Location

`data/FUN_company_pl_actuals_dataset.csv`

## Columns

| Column | Description |
|--------|-------------|
| Product | Product identifier |
| Country | Country name |
| Fiscal Year | Year (numeric) |
| Fiscal Quarter | Q1, Q2, Q3, Q4 |
| Fiscal Period | Period within quarter |
| FSLine Statement L1 | Top-level financial category |
| FSLine Statement L2 | Detailed line item |
| Amount in USD | USD value |
| Amount in Local Currency | Local currency value |

## Valid Values

### Products
- A, B, C, D (only these four exist - no others)

### Countries
- Australia, Canada, Germany, Japan, United Kingdom, United States

### Years
- 2020, 2021, 2022, 2023, 2024

### FSLine Statement L1 (Top-level categories)
- Net Revenue
- Cost of Goods Sold
- Operating Expenses
- Other Income/Expenses

### FSLine Statement L2 (Detailed line items)

**IMPORTANT**: When filtering by L2, use the exact values below. There is NO L2 value called "Revenue" or "Cost of Goods Sold" - those are L1 values.

| L1 Category | L2 Line Items |
|-------------|---------------|
| Net Revenue | `Gross Revenue`, `Returns and Refunds`, `Revenue Adjustment` |
| Cost of Goods Sold | `Direct Labor`, `Direct Materials`, `Manufacturing Overhead` |
| Operating Expenses | `General & Administrative`, `Headcount Expenses`, `IT Expenses`, `Marketing Expenses`, `R&D Expenses`, `Sales Expenses` |
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

## Edge Cases

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
