# Dataset Schema: FUN_company_pl_actuals_dataset.csv

## Columns
| Column | Type | Description |
|--------|------|-------------|
| Fiscal Year | int | 2020-2024 |
| Fiscal Quarter | str | Q1, Q2, Q3, Q4 |
| Fiscal Period | str | YYYY-MM format |
| FSLine Statement L1 | str | Net Revenue, Cost of Goods Sold, OPEX, Other Income/Expenses |
| FSLine Statement L2 | str | 15 detailed line items |
| Product | str | Product A, B, C, D |
| Country | str | Australia, Canada, Germany, Japan, United Kingdom, United States |
| Currency | str | AUD, CAD, EUR, GBP, JPY, USD |
| Amount in Local Currency | float | Amount in local currency |
| Amount in USD | float | **Use this for all calculations** |
| Version | str | Always "Actuals" |

## Valid Products
- Product A, Product B, Product C, Product D
- **No other products exist** (e.g., Product E does not exist)

## FSLine Statement L2 by L1
- **Net Revenue:** Gross Revenue, Returns and Refunds, Revenue Adjustment
- **Cost of Goods Sold:** Direct Labor, Direct Materials, Manufacturing Overhead
- **OPEX:** Marketing Expenses, R&D Expenses, Sales Expenses, General & Administrative, IT Expenses, Headcount Expenses
- **Other Income/Expenses:** Interest Income, Interest Expense, Foreign Exchange Gain/Loss

## Key Rules
1. Always use "Amount in USD" for monetary calculations
2. Quarter months: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
3. Returns and Refunds are negative values
4. FX Gain/Loss can be positive or negative
5. Net Revenue = sum of all rows where FSLine Statement L1 = "Net Revenue"
