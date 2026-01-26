"""
Learned Helper Functions

This file contains reusable helper functions extracted from repeated patterns.
The improver adds functions here when the same code pattern appears 3+ times.

HOW TO USE:
-----------
Import these functions in your analysis code:

    from knowledge.functions import validate_product, calculate_gross_profit

Each function includes:
- Docstring explaining purpose and parameters
- Type hints for inputs and outputs
- Example usage

WHEN TO ADD FUNCTIONS:
----------------------
The improver should add a function here when:
1. The same code pattern appears in 3+ different queries
2. The logic is non-trivial (more than 2-3 lines)
3. The function is generalizable (works with parameters, not hardcoded values)

TEMPLATE:
---------
def function_name(param1: type, param2: type) -> return_type:
    '''
    Brief description of what this function does.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter

    Returns:
        Description of return value

    Example:
        >>> result = function_name(value1, value2)
        >>> print(result)
        expected_output
    '''
    # Implementation
    return result
"""

import pandas as pd
from typing import Tuple, Optional, List

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================
# Add validation helpers here when learner repeatedly validates the same things

# Example (uncomment and modify when needed):
#
# def validate_product(product: str) -> Tuple[bool, str]:
#     '''
#     Check if a product exists in the dataset.
#
#     Args:
#         product: Product name to validate (e.g., "Product A")
#
#     Returns:
#         Tuple of (is_valid, message)
#         - If valid: (True, product_name)
#         - If invalid: (False, error_message)
#
#     Example:
#         >>> valid, msg = validate_product("Product E")
#         >>> print(valid, msg)
#         False "Product 'Product E' does not exist. Valid products: A, B, C, D"
#     '''
#     valid_products = {'Product A', 'Product B', 'Product C', 'Product D'}
#     if product in valid_products:
#         return True, product
#     return False, f"Product '{product}' does not exist. Valid products: {', '.join(sorted(valid_products))}"


# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================
# Add calculation helpers here when the same formula is used 3+ times

# Example (uncomment and modify when needed):
#
# def calculate_gross_profit(df: pd.DataFrame) -> float:
#     '''
#     Calculate gross profit from a filtered dataframe.
#
#     Formula: Gross Profit = Net Revenue - Cost of Goods Sold
#
#     Args:
#         df: DataFrame already filtered to desired scope (product, period, etc.)
#
#     Returns:
#         Gross profit as a float (can be negative)
#
#     Example:
#         >>> product_a = df[df['Product'] == 'Product A']
#         >>> gross_profit = calculate_gross_profit(product_a)
#     '''
#     revenue = df[df['FSLine Statement L1'] == 'Net Revenue']['Amount in USD'].sum()
#     cogs = df[df['FSLine Statement L1'] == 'Cost of Goods Sold']['Amount in USD'].sum()
#     return revenue - cogs


# =============================================================================
# AGGREGATION FUNCTIONS
# =============================================================================
# Add aggregation helpers here when the same grouping/pivot pattern repeats

def calculate_rolling_average_with_threshold(
    df: pd.DataFrame,
    l1_category: str,
    group_cols: List[str],
    period_col: str = 'Fiscal Period',
    window: int = 3,
    threshold_pct: float = 10.0
) -> pd.DataFrame:
    '''
    Calculate rolling average for a financial metric and flag values exceeding threshold.

    Args:
        df: Full P&L DataFrame
        l1_category: FSLine Statement L1 value (e.g., 'OPEX', 'Net Revenue')
        group_cols: Columns to group by (e.g., ['Product'])
        period_col: Column for time ordering (default: 'Fiscal Period')
        window: Rolling window size (default: 3)
        threshold_pct: Percentage threshold to flag exceedances (default: 10.0)

    Returns:
        DataFrame with columns: group_cols, period_col, 'Amount', 'Rolling_Avg',
        'Diff_Percentage', 'Exceeded_Threshold'

    Example:
        >>> from knowledge.functions import calculate_rolling_average_with_threshold
        >>> result = calculate_rolling_average_with_threshold(
        ...     df, l1_category='OPEX', group_cols=['Product'], threshold_pct=10.0
        ... )
        >>> exceeded = result[result['Exceeded_Threshold']]
    '''
    # Filter for the L1 category
    filtered = df[df['FSLine Statement L1'] == l1_category]

    # Group and sum
    grouped = filtered.groupby(group_cols + [period_col])['Amount in USD'].sum().reset_index()
    grouped = grouped.rename(columns={'Amount in USD': 'Amount'})

    # Sort for correct rolling calculation
    grouped = grouped.sort_values(group_cols + [period_col])

    # Calculate rolling average
    grouped['Rolling_Avg'] = grouped.groupby(group_cols)['Amount'].rolling(
        window=window, min_periods=1
    ).mean().reset_index(0, drop=True)

    # Calculate percentage difference
    grouped['Diff_Percentage'] = (
        (grouped['Amount'] - grouped['Rolling_Avg']) / grouped['Rolling_Avg'] * 100
    )

    # Flag exceedances
    grouped['Exceeded_Threshold'] = grouped['Diff_Percentage'] > threshold_pct

    return grouped


# =============================================================================
# COMPARISON FUNCTIONS
# =============================================================================
# Add comparison helpers here for multi-product/multi-metric analysis

def compare_products_on_metrics(
    df: pd.DataFrame,
    product_a: str,
    product_b: str,
    group_cols: List[str] = None
) -> pd.DataFrame:
    '''
    Compare two products on Revenue, COGS, and Gross Margin.

    This function handles the complexity of:
    1. Filtering by FSLine Statement L1 for each metric
    2. Aggregating by product and grouping columns
    3. Merging and pivoting to compare products side-by-side
    4. Calculating gross margin percentage

    Args:
        df: Full P&L DataFrame
        product_a: First product name (e.g., 'Product A')
        product_b: Second product name (e.g., 'Product B')
        group_cols: Columns to group by (default: ['Country', 'Fiscal Year', 'Fiscal Period'])

    Returns:
        DataFrame with columns:
        - group_cols (Country, Fiscal Year, Fiscal Period)
        - Revenue_A, Revenue_B
        - COGS_A, COGS_B
        - Gross_Margin_Pct_A, Gross_Margin_Pct_B

    Example:
        >>> from knowledge.functions import compare_products_on_metrics
        >>> comparison = compare_products_on_metrics(df, 'Product A', 'Product B')
        >>> # Find where A has higher revenue but lower margin than B
        >>> result = comparison[
        ...     (comparison['Revenue_A'] > comparison['Revenue_B']) &
        ...     (comparison['Gross_Margin_Pct_A'] < comparison['Gross_Margin_Pct_B'])
        ... ]
    '''
    if group_cols is None:
        group_cols = ['Country', 'Fiscal Year', 'Fiscal Period']

    # Filter for the two products
    df_filtered = df[df['Product'].isin([product_a, product_b])]

    # Get Revenue by Product and grouping columns
    revenue = (
        df_filtered[df_filtered['FSLine Statement L1'] == 'Net Revenue']
        .groupby(['Product'] + group_cols)['Amount in USD']
        .sum()
        .reset_index()
        .rename(columns={'Amount in USD': 'Revenue'})
    )

    # Get COGS by Product and grouping columns
    cogs = (
        df_filtered[df_filtered['FSLine Statement L1'] == 'Cost of Goods Sold']
        .groupby(['Product'] + group_cols)['Amount in USD']
        .sum()
        .reset_index()
        .rename(columns={'Amount in USD': 'COGS'})
    )

    # Merge Revenue and COGS
    metrics = revenue.merge(cogs, on=['Product'] + group_cols, how='outer').fillna(0)

    # Calculate Gross Margin Percentage
    metrics['Gross_Margin_Pct'] = (
        (metrics['Revenue'] - metrics['COGS']) / metrics['Revenue'] * 100
    ).fillna(0)

    # Pivot to get side-by-side comparison
    pivot_rev = metrics.pivot_table(
        index=group_cols,
        columns='Product',
        values='Revenue'
    ).reset_index()
    pivot_rev.columns = [col if col in group_cols else f'Revenue_{col.replace("Product ", "")}'
                         for col in pivot_rev.columns]

    pivot_cogs = metrics.pivot_table(
        index=group_cols,
        columns='Product',
        values='COGS'
    ).reset_index()
    pivot_cogs.columns = [col if col in group_cols else f'COGS_{col.replace("Product ", "")}'
                          for col in pivot_cogs.columns]

    pivot_margin = metrics.pivot_table(
        index=group_cols,
        columns='Product',
        values='Gross_Margin_Pct'
    ).reset_index()
    pivot_margin.columns = [col if col in group_cols else f'Gross_Margin_Pct_{col.replace("Product ", "")}'
                            for col in pivot_margin.columns]

    # Merge all pivots
    result = pivot_rev.merge(pivot_cogs, on=group_cols)
    result = result.merge(pivot_margin, on=group_cols)

    return result


# =============================================================================
# FILTERING FUNCTIONS
# =============================================================================
# Add filtering helpers here when complex filter logic is reused
