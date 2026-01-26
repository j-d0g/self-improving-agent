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
# FILTERING FUNCTIONS
# =============================================================================
# Add filtering helpers here when complex filter logic is reused
