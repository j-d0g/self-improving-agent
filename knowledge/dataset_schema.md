# Financial Dataset Schema

## Overview
- **File**: `FUN_company_pl_actuals_dataset.csv`
- **Rows**: 21,601 rows of financial data
- **Time Range**: 2020-2024 (5 years, 20 quarters)
- **Granularity**: Monthly data within quarters

## Columns

| Column | Type | Description |
|--------|------|-------------|
| Fiscal Year | int | Year (2020-2024) |
| Fiscal Quarter | str | Quarter label (Q1, Q2, Q3, Q4) |
| Fiscal Period | str | Month in YYYY-MM format |
| FSLine Statement L1 | str | High-level financial category |
| FSLine Statement L2 | str | Detailed line item |
| Product | str | Product name |
| Country | str | Country name |
| Currency | str | Local currency code |
| Amount in Local Currency | float | Amount in local currency |
| Amount in USD | float | Amount converted to USD |
| Version | str | Always "Actuals" |

## Valid Values

### Products (4 total)
- Product A
- Product B
- Product C
- Product D

### Countries (6 total)
- Australia
- Canada
- Germany
- Japan
- United Kingdom
- United States

### Currencies
- AUD (Australia)
- CAD (Canada)
- EUR (Germany)
- GBP (United Kingdom)
- JPY (Japan)
- USD (United States)

### FSLine Statement L1 (4 categories)
- **Net Revenue**: Sales and revenue items
- **Cost of Goods Sold**: Direct production costs (also abbreviated as COGS)
- **OPEX**: Operating expenses
- **Other Income/Expenses**: Non-operating items

### FSLine Statement L2 (15 line items)

**Under Net Revenue:**
- Gross Revenue (positive)
- Returns and Refunds (negative)
- Revenue Adjustment (can be positive or negative)

**Under Cost of Goods Sold:**
- Direct Labor
- Direct Materials
- Manufacturing Overhead

**Under OPEX:**
- Marketing Expenses
- R&D Expenses
- Sales Expenses
- General & Administrative
- IT Expenses
- Headcount Expenses

**Under Other Income/Expenses:**
- Interest Income
- Interest Expense
- Foreign Exchange Gain/Loss

## Important Calculations

### Net Revenue Calculation
Net Revenue = Gross Revenue + Returns and Refunds + Revenue Adjustment
(Note: Returns are typically negative values)

### Operating Margin
Operating Margin = (Net Revenue - COGS - OPEX) / Net Revenue

### Quarter to Months Mapping
- Q1: January, February, March (months 01, 02, 03)
- Q2: April, May, June (months 04, 05, 06)
- Q3: July, August, September (months 07, 08, 09)
- Q4: October, November, December (months 10, 11, 12)

## Common Pitfalls

1. **Quarter filtering**: A quarter contains 3 months. Filter by Fiscal Quarter column OR filter Fiscal Period for all 3 months.
2. **Revenue vs Gross Revenue**: "Revenue" typically means Net Revenue (sum of all L1="Net Revenue" items), not just Gross Revenue.
3. **Negative values**: Returns, Refunds, and some adjustments are negative.
4. **Currency**: Use "Amount in USD" for cross-country comparisons.
5. **Non-existent data**: Only Products A-D exist. Only the listed L2 items exist.
