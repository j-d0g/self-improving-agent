"""
Verification Module for Self-Improving Agent

Implements a layered verification approach (gather-act-verify pattern):
1. Execution checks (instant, deterministic) - catch code execution failures
2. Data shape checks (fast, deterministic) - validate DataFrame structure
3. Value/domain checks (fast, domain-specific) - financial accounting rules
4. LLM judge (expensive, semantic) - optional fallback for complex validation

The goal: catch as many errors programmatically before resorting to LLM evaluation.
Research shows self-correction works best with reliable external/programmatic feedback.

References:
- "When Can LLMs Actually Correct Their Own Mistakes?" (TACL 2024)
- Claude Agent SDK gather-act-verify patterns
- MAST taxonomy for agent failure modes
"""

import re
import pandas as pd
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, List, Dict
from enum import Enum


class ErrorCategory(Enum):
    """High-level error categories for learning guidance."""
    CODE_GENERATION = "code_generation"  # Syntax, import, name errors
    TYPE_MISMATCH = "type_mismatch"      # TypeError, wrong type
    VALUE_ERROR = "value_error"          # ValueError, invalid values
    DATA_ACCESS = "data_access"          # KeyError, IndexError, column access
    LOGIC_ERROR = "logic_error"          # Wrong results, failed checks
    TIMEOUT = "timeout"                  # Execution timeout
    UNKNOWN = "unknown"


class ErrorType(Enum):
    """Classification of errors detected during verification."""
    # Execution errors (Layer 1)
    SYNTAX_ERROR = "syntax_error"        # Code generation failed
    NAME_ERROR = "name_error"            # Undefined variable/function
    IMPORT_ERROR = "import_error"        # Module not available
    TYPE_ERROR = "type_error"            # Type mismatch in operation
    VALUE_ERROR = "value_error"          # Correct type, wrong value
    KEY_ERROR = "key_error"              # Dict/DataFrame key not found
    INDEX_ERROR = "index_error"          # List/array index out of bounds
    ATTRIBUTE_ERROR = "attribute_error"  # Object has no attribute
    EXCEPTION = "exception"              # Generic/uncategorized exception
    TIMEOUT = "timeout"
    NO_RESULT = "no_result"
    WRONG_TYPE = "wrong_type"

    # Data shape errors (Layer 2)
    EMPTY_RESULT = "empty_result"
    MISSING_COLUMNS = "missing_columns"
    TOO_FEW_ROWS = "too_few_rows"
    TOO_MANY_ROWS = "too_many_rows"
    UNEXPECTED_NULLS = "unexpected_nulls"
    DUPLICATE_ROWS = "duplicate_rows"

    # Value/domain errors (Layer 3)
    NEGATIVE_WHEN_POSITIVE_EXPECTED = "negative_value"
    VALUE_OUT_OF_RANGE = "value_out_of_range"
    FAILED_IDENTITY_CHECK = "identity_check_failed"
    MAGNITUDE_ANOMALY = "magnitude_anomaly"
    TEMPORAL_INCONSISTENCY = "temporal_inconsistency"
    MARGIN_EXCEEDS_100 = "margin_exceeds_100"
    MARGIN_HIERARCHY_VIOLATED = "margin_hierarchy_violated"
    GROWTH_RATE_ANOMALY = "growth_rate_anomaly"

    # Semantic errors (from LLM judge - Layer 4)
    ANSWER_MISMATCH = "answer_mismatch"
    REASONING_ERROR = "reasoning_error"


# Map exception types to error types and categories for learning guidance
EXCEPTION_MAPPING = {
    "SyntaxError": (ErrorType.SYNTAX_ERROR, ErrorCategory.CODE_GENERATION,
                    "Code has invalid Python syntax - check for missing colons, brackets, quotes"),
    "NameError": (ErrorType.NAME_ERROR, ErrorCategory.CODE_GENERATION,
                  "Variable or function not defined - check spelling and imports"),
    "ImportError": (ErrorType.IMPORT_ERROR, ErrorCategory.CODE_GENERATION,
                    "Module not found - use only available libraries"),
    "ModuleNotFoundError": (ErrorType.IMPORT_ERROR, ErrorCategory.CODE_GENERATION,
                            "Module not installed - use only pandas/numpy"),
    "TypeError": (ErrorType.TYPE_ERROR, ErrorCategory.TYPE_MISMATCH,
                  "Type mismatch - check data types before operations"),
    "ValueError": (ErrorType.VALUE_ERROR, ErrorCategory.VALUE_ERROR,
                   "Invalid value - check input constraints"),
    "KeyError": (ErrorType.KEY_ERROR, ErrorCategory.DATA_ACCESS,
                 "Column or key not found - verify column names in schema"),
    "IndexError": (ErrorType.INDEX_ERROR, ErrorCategory.DATA_ACCESS,
                   "Index out of bounds - check array/list length"),
    "AttributeError": (ErrorType.ATTRIBUTE_ERROR, ErrorCategory.DATA_ACCESS,
                       "Object has no such attribute - check object type"),
}


class Severity(Enum):
    """Severity level for verification results."""
    ERROR = "error"      # Must fix - execution failed or data invalid
    WARNING = "warning"  # Should investigate - may be legitimate edge case
    INFO = "info"        # Informational only


@dataclass
class VerificationResult:
    """Result of running a single verification check."""
    passed: bool
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    layer: str = ""  # Which verification layer caught this
    severity: Severity = Severity.ERROR
    category: Optional[ErrorCategory] = None
    recovery_hint: Optional[str] = None  # Guidance for self-correction
    details: dict = field(default_factory=dict)

    @staticmethod
    def success() -> "VerificationResult":
        return VerificationResult(passed=True)

    @staticmethod
    def failure(
        error_type: ErrorType,
        message: str,
        layer: str,
        severity: Severity = Severity.ERROR,
        category: ErrorCategory = None,
        recovery_hint: str = None,
        **details
    ) -> "VerificationResult":
        return VerificationResult(
            passed=False,
            error_type=error_type,
            error_message=message,
            layer=layer,
            severity=severity,
            category=category,
            recovery_hint=recovery_hint,
            details=details
        )


@dataclass
class VerificationReport:
    """Aggregated report of all verification checks run."""
    results: List[VerificationResult] = field(default_factory=list)

    def add(self, result: VerificationResult):
        """Add a result to the report."""
        self.results.append(result)

    @property
    def passed(self) -> bool:
        """True if no ERROR-severity failures."""
        return all(
            r.passed or r.severity != Severity.ERROR
            for r in self.results
        )

    @property
    def errors(self) -> List[VerificationResult]:
        """Get all error-level failures."""
        return [r for r in self.results
                if not r.passed and r.severity == Severity.ERROR]

    @property
    def warnings(self) -> List[VerificationResult]:
        """Get all warnings."""
        return [r for r in self.results
                if not r.passed and r.severity == Severity.WARNING]

    @property
    def first_error(self) -> Optional[VerificationResult]:
        """Get the first error (most likely cause)."""
        errors = self.errors
        return errors[0] if errors else None

    def summary(self) -> str:
        """Human-readable summary of verification results."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        errors = len(self.errors)
        warnings = len(self.warnings)
        return f"Verification: {passed}/{total} passed, {errors} errors, {warnings} warnings"

    def to_feedback(self) -> str:
        """Generate feedback string for agent self-correction."""
        if self.passed:
            return "All verification checks passed."

        feedback_parts = []
        for result in self.errors:
            msg = f"[{result.layer.upper()}] {result.error_message}"
            if result.recovery_hint:
                msg += f" | Hint: {result.recovery_hint}"
            feedback_parts.append(msg)

        return "\n".join(feedback_parts)


class ExceptionClassifier:
    """
    Classifies Python exceptions to provide semantic meaning for learning.

    Exception types tell us different things:
    - SyntaxError: Code generation issue - the agent wrote invalid Python
    - NameError: Variable not defined - likely typo or missing import
    - TypeError: Type mismatch - wrong data types in operation
    - ValueError: Right type, wrong value - constraint violation
    - KeyError/IndexError: Data access issue - wrong column/index
    """

    # Patterns to extract exception type from traceback strings
    EXCEPTION_PATTERNS = [
        r"(\w+Error):\s*(.+?)(?:\n|$)",
        r"(\w+Exception):\s*(.+?)(?:\n|$)",
        r"Execution error:\s*(\w+):\s*(.+?)(?:\n|$)",
    ]

    @classmethod
    def classify(cls, error_string: str) -> VerificationResult:
        """
        Classify an exception from its error string/traceback.

        Returns a VerificationResult with:
        - error_type: Specific ErrorType for the exception
        - category: High-level ErrorCategory for learning
        - recovery_hint: Guidance for fixing the issue
        """
        if not error_string:
            return VerificationResult.success()

        # Try to extract exception type and message
        exception_type = None
        exception_msg = ""

        for pattern in cls.EXCEPTION_PATTERNS:
            match = re.search(pattern, error_string)
            if match:
                exception_type = match.group(1)
                exception_msg = match.group(2).strip()
                break

        if not exception_type:
            # Check for common error indicators
            if "Traceback" in error_string:
                # Try to find error at the end
                lines = error_string.strip().split('\n')
                for line in reversed(lines):
                    if 'Error:' in line or 'Exception:' in line:
                        parts = line.split(':', 1)
                        exception_type = parts[0].strip().split()[-1]
                        exception_msg = parts[1].strip() if len(parts) > 1 else ""
                        break

        if not exception_type:
            return VerificationResult.failure(
                ErrorType.EXCEPTION,
                "Unknown execution error",
                layer="execution",
                category=ErrorCategory.UNKNOWN,
                recovery_hint="Check the full error output for details",
                raw_error=error_string[:500]
            )

        # Look up the exception in our mapping
        if exception_type in EXCEPTION_MAPPING:
            error_type, category, hint = EXCEPTION_MAPPING[exception_type]
            return VerificationResult.failure(
                error_type,
                f"{exception_type}: {exception_msg}",
                layer="execution",
                category=category,
                recovery_hint=hint,
                exception_type=exception_type,
                exception_message=exception_msg
            )

        # Unknown exception type
        return VerificationResult.failure(
            ErrorType.EXCEPTION,
            f"{exception_type}: {exception_msg}",
            layer="execution",
            category=ErrorCategory.UNKNOWN,
            recovery_hint="Check the exception type and fix accordingly",
            exception_type=exception_type,
            exception_message=exception_msg
        )


class ExecutionVerifier:
    """Layer 1: Verify code execution basics."""

    # Error indicators in execution output
    ERROR_INDICATORS = [
        "Execution error:",
        "Traceback (most recent call last)",
        "Error:",
        "Exception:",
    ]

    # Timeout indicators
    TIMEOUT_INDICATORS = [
        "TimeoutError",
        "execution timed out",
        "exceeded time limit",
    ]

    @classmethod
    def check_exception(cls, result: str) -> VerificationResult:
        """
        Check if execution resulted in an exception.
        Uses ExceptionClassifier for semantic classification.
        """
        # Check for timeout first (special case)
        for indicator in cls.TIMEOUT_INDICATORS:
            if indicator.lower() in result.lower():
                return VerificationResult.failure(
                    ErrorType.TIMEOUT,
                    "Code execution timed out",
                    layer="execution",
                    category=ErrorCategory.TIMEOUT,
                    recovery_hint="Simplify the query or add row limits",
                    raw_error=result[:500]
                )

        # Check for any error indicators
        has_error = any(indicator in result for indicator in cls.ERROR_INDICATORS)

        if has_error:
            # Use classifier for detailed analysis
            return ExceptionClassifier.classify(result)

        return VerificationResult.success()

    @staticmethod
    def check_result_exists(result: Any) -> VerificationResult:
        """Check if a result was produced."""
        if result is None:
            return VerificationResult.failure(
                ErrorType.NO_RESULT,
                "No result was returned",
                layer="execution",
                category=ErrorCategory.CODE_GENERATION,
                recovery_hint="Ensure code assigns a value to the 'result' variable"
            )
        if isinstance(result, str) and "result variable was not set" in result.lower():
            return VerificationResult.failure(
                ErrorType.NO_RESULT,
                "Code did not set the 'result' variable",
                layer="execution",
                category=ErrorCategory.CODE_GENERATION,
                recovery_hint="Add 'result = <your_answer>' at the end of the code"
            )
        return VerificationResult.success()

    @staticmethod
    def check_type(result: Any, expected_types: tuple) -> VerificationResult:
        """Check if result is of expected type."""
        if not isinstance(result, expected_types):
            return VerificationResult.failure(
                ErrorType.WRONG_TYPE,
                f"Expected {expected_types}, got {type(result).__name__}",
                layer="execution",
                category=ErrorCategory.TYPE_MISMATCH,
                recovery_hint=f"Convert result to one of: {expected_types}",
                actual_type=type(result).__name__
            )
        return VerificationResult.success()


class DataShapeVerifier:
    """Layer 2: Verify DataFrame/result shape properties."""

    @staticmethod
    def check_not_empty(df: pd.DataFrame) -> VerificationResult:
        """Check if DataFrame has rows."""
        if df.empty:
            return VerificationResult.failure(
                ErrorType.EMPTY_RESULT,
                "Query returned empty DataFrame - filter may be too restrictive",
                layer="data_shape",
                severity=Severity.ERROR,
                category=ErrorCategory.DATA_ACCESS,
                recovery_hint="Verify filter values match data - check column values with df['col'].unique()",
                columns=list(df.columns)
            )
        return VerificationResult.success()

    @staticmethod
    def check_row_count(
        df: pd.DataFrame,
        min_rows: int = None,
        max_rows: int = None
    ) -> VerificationResult:
        """Check if row count is in expected range."""
        row_count = len(df)
        if min_rows is not None and row_count < min_rows:
            return VerificationResult.failure(
                ErrorType.TOO_FEW_ROWS,
                f"Expected at least {min_rows} rows, got {row_count}",
                layer="data_shape",
                severity=Severity.WARNING,
                category=ErrorCategory.DATA_ACCESS,
                recovery_hint="Filter may be too restrictive - try broadening criteria",
                row_count=row_count,
                expected_min=min_rows
            )
        if max_rows is not None and row_count > max_rows:
            return VerificationResult.failure(
                ErrorType.TOO_MANY_ROWS,
                f"Expected at most {max_rows} rows, got {row_count}",
                layer="data_shape",
                severity=Severity.WARNING,
                category=ErrorCategory.DATA_ACCESS,
                recovery_hint="Filter may be too broad - add more specific criteria",
                row_count=row_count,
                expected_max=max_rows
            )
        return VerificationResult.success()

    @staticmethod
    def check_no_nulls(df: pd.DataFrame, columns: List[str] = None) -> VerificationResult:
        """Check for unexpected null values."""
        cols_to_check = columns or df.columns.tolist()
        null_cols = []
        for col in cols_to_check:
            if col in df.columns and df[col].isna().any():
                null_count = int(df[col].isna().sum())
                null_cols.append((col, null_count))

        if null_cols:
            return VerificationResult.failure(
                ErrorType.UNEXPECTED_NULLS,
                f"Found null values in columns: {[c[0] for c in null_cols]}",
                layer="data_shape",
                severity=Severity.WARNING,
                category=ErrorCategory.DATA_ACCESS,
                recovery_hint="Use .dropna() or .fillna() to handle missing values",
                null_columns=null_cols
            )
        return VerificationResult.success()

    @staticmethod
    def check_columns_exist(df: pd.DataFrame, required_columns: List[str]) -> VerificationResult:
        """Check if required columns are present."""
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            return VerificationResult.failure(
                ErrorType.MISSING_COLUMNS,
                f"Missing required columns: {missing}",
                layer="data_shape",
                severity=Severity.ERROR,
                category=ErrorCategory.DATA_ACCESS,
                recovery_hint=f"Available columns: {list(df.columns)}",
                missing_columns=missing,
                available_columns=list(df.columns)
            )
        return VerificationResult.success()

    @staticmethod
    def check_no_duplicates(
        df: pd.DataFrame,
        subset: List[str] = None
    ) -> VerificationResult:
        """Check for unexpected duplicate rows."""
        dup_count = df.duplicated(subset=subset).sum()
        if dup_count > 0:
            return VerificationResult.failure(
                ErrorType.DUPLICATE_ROWS,
                f"Found {dup_count} duplicate rows",
                layer="data_shape",
                severity=Severity.WARNING,
                category=ErrorCategory.DATA_ACCESS,
                recovery_hint="Use .drop_duplicates() if duplicates are unexpected",
                duplicate_count=int(dup_count),
                subset=subset
            )
        return VerificationResult.success()

    @staticmethod
    def check_unique_values(
        df: pd.DataFrame,
        column: str,
        expected_values: List[Any] = None
    ) -> VerificationResult:
        """Check if column has expected unique values."""
        if column not in df.columns:
            return VerificationResult.failure(
                ErrorType.MISSING_COLUMNS,
                f"Column '{column}' not found",
                layer="data_shape",
                severity=Severity.ERROR,
                category=ErrorCategory.DATA_ACCESS
            )

        actual_values = set(df[column].unique())
        if expected_values:
            expected_set = set(expected_values)
            missing = expected_set - actual_values
            extra = actual_values - expected_set

            if missing or extra:
                return VerificationResult.failure(
                    ErrorType.VALUE_OUT_OF_RANGE,
                    f"Column '{column}' has unexpected values",
                    layer="data_shape",
                    severity=Severity.WARNING,
                    category=ErrorCategory.DATA_ACCESS,
                    recovery_hint=f"Expected: {expected_values}, Got: {list(actual_values)}",
                    missing_values=list(missing),
                    extra_values=list(extra)
                )
        return VerificationResult.success()


class FinancialDomainVerifier:
    """
    Layer 3: Verify financial domain-specific rules.

    Implements accounting identities and business logic checks:
    - Sign conventions (revenue >= 0, costs >= 0, etc.)
    - Accounting identities (GP = Revenue - COGS)
    - Temporal consistency (Q1+Q2+Q3+Q4 = Annual)
    - Cross-validation (margin calculations, hierarchy)
    - Magnitude sanity checks
    """

    @staticmethod
    def check_revenue_positive(value: float, allow_negative_for_returns: bool = False) -> VerificationResult:
        """Revenue should generally be positive."""
        if value < 0 and not allow_negative_for_returns:
            return VerificationResult.failure(
                ErrorType.NEGATIVE_WHEN_POSITIVE_EXPECTED,
                f"Revenue is negative ({value:,.2f}) - unexpected unless this is returns/refunds",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Check filter conditions - negative revenue suggests wrong data slice",
                value=value
            )
        return VerificationResult.success()

    @staticmethod
    def check_cost_positive(value: float, cost_name: str = "Cost") -> VerificationResult:
        """Costs (COGS, OPEX, etc.) should be positive or zero."""
        if value < 0:
            return VerificationResult.failure(
                ErrorType.NEGATIVE_WHEN_POSITIVE_EXPECTED,
                f"{cost_name} is negative ({value:,.2f})",
                layer="domain",
                severity=Severity.WARNING,  # Could be legitimate (reversals)
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint=f"Verify {cost_name} sign convention in the data",
                value=value
            )
        return VerificationResult.success()

    @staticmethod
    def check_percentage_range(value: float, name: str = "percentage") -> VerificationResult:
        """Percentages/margins should typically be in reasonable range."""
        # Assuming value is already in percentage form (e.g., 50 for 50%)
        if value < -200 or value > 200:
            return VerificationResult.failure(
                ErrorType.VALUE_OUT_OF_RANGE,
                f"{name} value {value:.2f}% seems out of reasonable range (-200% to 200%)",
                layer="domain",
                severity=Severity.WARNING,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Check if percentage calculation is correct",
                value=value
            )
        return VerificationResult.success()

    @staticmethod
    def check_margin_not_exceeds_100(value: float, name: str = "Gross margin") -> VerificationResult:
        """Gross margin cannot exceed 100% (can't make more than revenue)."""
        # Assuming value is decimal (0.5 = 50%)
        if value > 1.0:
            return VerificationResult.failure(
                ErrorType.MARGIN_EXCEEDS_100,
                f"{name} ({value:.1%}) exceeds 100% - mathematically impossible",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Check numerator/denominator order in margin calculation",
                value=value
            )
        return VerificationResult.success()

    @staticmethod
    def check_margin_hierarchy(
        gross_margin: float,
        operating_margin: float,
        net_margin: float = None
    ) -> VerificationResult:
        """
        Check margin hierarchy: Gross >= Operating >= Net (typically).
        Note: Can be violated with significant other income.
        """
        if gross_margin < operating_margin:
            return VerificationResult.failure(
                ErrorType.MARGIN_HIERARCHY_VIOLATED,
                f"Operating margin ({operating_margin:.1%}) > Gross margin ({gross_margin:.1%})",
                layer="domain",
                severity=Severity.WARNING,  # Can happen with other income
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify calculation or check for significant other operating income",
                gross_margin=gross_margin,
                operating_margin=operating_margin
            )

        if net_margin is not None and operating_margin < net_margin:
            return VerificationResult.failure(
                ErrorType.MARGIN_HIERARCHY_VIOLATED,
                f"Net margin ({net_margin:.1%}) > Operating margin ({operating_margin:.1%})",
                layer="domain",
                severity=Severity.WARNING,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify calculation or check for significant non-operating income",
                operating_margin=operating_margin,
                net_margin=net_margin
            )

        return VerificationResult.success()

    @staticmethod
    def check_quarters_sum_to_year(
        q1: float, q2: float, q3: float, q4: float,
        annual: float,
        tolerance: float = 0.01
    ) -> VerificationResult:
        """Check that quarters sum to annual total."""
        quarters_sum = q1 + q2 + q3 + q4
        diff = abs(quarters_sum - annual)
        relative_diff = diff / abs(annual) if annual != 0 else diff

        if relative_diff > tolerance:
            return VerificationResult.failure(
                ErrorType.TEMPORAL_INCONSISTENCY,
                f"Quarters ({quarters_sum:,.2f}) don't sum to annual ({annual:,.2f}), diff: {relative_diff:.1%}",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Check fiscal period filtering - ensure all 4 quarters are included",
                quarters_sum=quarters_sum,
                annual=annual,
                difference=diff,
                relative_diff=relative_diff
            )
        return VerificationResult.success()

    @staticmethod
    def check_gross_profit_identity(
        revenue: float,
        cogs: float,
        gross_profit: float,
        tolerance: float = 0.01
    ) -> VerificationResult:
        """Check: Gross Profit = Revenue - COGS."""
        expected = revenue - cogs
        diff = abs(expected - gross_profit)
        relative_diff = diff / abs(expected) if expected != 0 else diff

        if relative_diff > tolerance:
            return VerificationResult.failure(
                ErrorType.FAILED_IDENTITY_CHECK,
                f"Gross Profit identity failed: {revenue:,.0f} - {cogs:,.0f} = {expected:,.0f}, but got {gross_profit:,.0f}",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify column names for Revenue, COGS, and Gross Profit",
                expected=expected,
                actual=gross_profit,
                difference=diff
            )
        return VerificationResult.success()

    @staticmethod
    def check_operating_income_identity(
        gross_profit: float,
        opex: float,
        operating_income: float,
        tolerance: float = 0.01
    ) -> VerificationResult:
        """Check: Operating Income = Gross Profit - Operating Expenses."""
        expected = gross_profit - opex
        diff = abs(expected - operating_income)
        relative_diff = diff / abs(expected) if expected != 0 else diff

        if relative_diff > tolerance:
            return VerificationResult.failure(
                ErrorType.FAILED_IDENTITY_CHECK,
                f"Operating Income identity failed: {gross_profit:,.0f} - {opex:,.0f} = {expected:,.0f}, but got {operating_income:,.0f}",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Check if all operating expenses are included",
                expected=expected,
                actual=operating_income,
                difference=diff
            )
        return VerificationResult.success()

    @staticmethod
    def check_accounting_identity(
        revenue: float,
        cogs: float,
        opex: float,
        operating_income: float,
        tolerance: float = 0.01
    ) -> VerificationResult:
        """Check: Revenue - COGS - OPEX = Operating Income."""
        expected = revenue - cogs - opex
        diff = abs(expected - operating_income)
        relative_diff = diff / abs(expected) if expected != 0 else diff

        if relative_diff > tolerance:
            return VerificationResult.failure(
                ErrorType.FAILED_IDENTITY_CHECK,
                f"Accounting identity failed: {revenue:,.0f} - {cogs:,.0f} - {opex:,.0f} = {expected:,.0f}, but got {operating_income:,.0f}",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify all components use consistent time periods and entities",
                expected=expected,
                actual=operating_income,
                difference=diff
            )
        return VerificationResult.success()

    @staticmethod
    def check_margin_calculation(
        numerator: float,
        denominator: float,
        reported_margin: float,
        margin_name: str = "margin",
        tolerance: float = 0.001
    ) -> VerificationResult:
        """Verify a margin is correctly calculated as numerator/denominator."""
        if denominator == 0:
            if reported_margin != 0:
                return VerificationResult.failure(
                    ErrorType.FAILED_IDENTITY_CHECK,
                    f"{margin_name} should be 0 or undefined when denominator is 0",
                    layer="domain",
                    severity=Severity.WARNING,
                    category=ErrorCategory.LOGIC_ERROR,
                    recovery_hint="Handle division by zero case"
                )
            return VerificationResult.success()

        expected = numerator / denominator
        diff = abs(expected - reported_margin)

        if diff > tolerance:
            return VerificationResult.failure(
                ErrorType.FAILED_IDENTITY_CHECK,
                f"{margin_name} mismatch: {numerator:,.0f}/{denominator:,.0f} = {expected:.4f}, but got {reported_margin:.4f}",
                layer="domain",
                severity=Severity.ERROR,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify margin formula uses correct numerator and denominator",
                expected=expected,
                actual=reported_margin,
                difference=diff
            )
        return VerificationResult.success()

    @staticmethod
    def check_growth_rate_sanity(
        current: float,
        previous: float,
        metric_name: str = "value",
        max_growth: float = 5.0,    # 500%
        max_decline: float = -0.99  # 99% decline
    ) -> VerificationResult:
        """Check if growth rate is within reasonable bounds."""
        if previous == 0:
            return VerificationResult.success()  # Can't calculate growth from zero

        growth_rate = (current - previous) / abs(previous)

        if growth_rate < max_decline or growth_rate > max_growth:
            return VerificationResult.failure(
                ErrorType.GROWTH_RATE_ANOMALY,
                f"{metric_name} growth of {growth_rate:.1%} seems extreme (expected {max_decline:.0%} to {max_growth:.0%})",
                layer="domain",
                severity=Severity.WARNING,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify time period comparison is correct",
                growth_rate=growth_rate,
                current=current,
                previous=previous
            )
        return VerificationResult.success()

    @staticmethod
    def check_magnitude(
        value: float,
        typical_min: float,
        typical_max: float,
        name: str = "value"
    ) -> VerificationResult:
        """Check if value is within expected magnitude."""
        if value < typical_min or value > typical_max:
            return VerificationResult.failure(
                ErrorType.MAGNITUDE_ANOMALY,
                f"{name} ({value:,.2f}) outside typical range [{typical_min:,.0f}, {typical_max:,.0f}]",
                layer="domain",
                severity=Severity.WARNING,
                category=ErrorCategory.LOGIC_ERROR,
                recovery_hint="Verify units and filters are correct",
                value=value,
                expected_range=(typical_min, typical_max)
            )
        return VerificationResult.success()


class VerificationPipeline:
    """
    Runs verification checks in layers, collecting all results.

    Layer 1: Execution - Did the code run without errors?
    Layer 2: Data Shape - Does the result have expected structure?
    Layer 3: Domain - Do values satisfy financial/business rules?
    Layer 4: (External) LLM Judge - Does the answer make semantic sense?

    Usage:
        pipeline = VerificationPipeline()
        report = pipeline.verify_full(execution_result, df, context)
        if not report.passed:
            feedback = report.to_feedback()
    """

    def __init__(self):
        self.execution = ExecutionVerifier()
        self.data_shape = DataShapeVerifier()
        self.domain = FinancialDomainVerifier()

    def verify_execution_result(self, result_str: str) -> VerificationResult:
        """Run Layer 1 checks on raw execution result string."""
        # Check for exceptions (uses classifier for semantic analysis)
        check = self.execution.check_exception(result_str)
        if not check.passed:
            return check

        # Check result exists
        check = self.execution.check_result_exists(result_str)
        if not check.passed:
            return check

        return VerificationResult.success()

    def verify_dataframe(
        self,
        df: pd.DataFrame,
        min_rows: int = None,
        max_rows: int = None,
        required_columns: List[str] = None,
        no_null_columns: List[str] = None,
        check_duplicates: bool = False
    ) -> VerificationReport:
        """Run Layer 2 checks on DataFrame result, collecting all issues."""
        report = VerificationReport()

        # Check not empty
        report.add(self.data_shape.check_not_empty(df))
        if report.errors:  # If empty, skip other checks
            return report

        # Check row count
        if min_rows is not None or max_rows is not None:
            report.add(self.data_shape.check_row_count(df, min_rows, max_rows))

        # Check columns
        if required_columns:
            report.add(self.data_shape.check_columns_exist(df, required_columns))

        # Check nulls
        if no_null_columns:
            report.add(self.data_shape.check_no_nulls(df, no_null_columns))

        # Check duplicates
        if check_duplicates:
            report.add(self.data_shape.check_no_duplicates(df))

        return report

    def verify_financial_value(
        self,
        value: float,
        value_type: str = "amount",  # "amount", "revenue", "percentage", "margin"
        typical_range: tuple = None
    ) -> VerificationReport:
        """Run Layer 3 checks on a financial value."""
        report = VerificationReport()

        if value_type == "revenue":
            report.add(self.domain.check_revenue_positive(value))

        if value_type in ("percentage", "margin"):
            report.add(self.domain.check_percentage_range(value, value_type))
            # Also check margin doesn't exceed 100%
            if value_type == "margin":
                report.add(self.domain.check_margin_not_exceeds_100(value))

        if typical_range:
            report.add(self.domain.check_magnitude(
                value, typical_range[0], typical_range[1], value_type
            ))

        return report

    def verify_full(
        self,
        execution_result: str,
        df: pd.DataFrame = None,
        value: float = None,
        value_type: str = "amount",
        **kwargs
    ) -> VerificationReport:
        """
        Run full verification pipeline across all layers.

        Returns a VerificationReport with all checks run.
        """
        report = VerificationReport()

        # Layer 1: Execution
        exec_check = self.verify_execution_result(execution_result)
        report.add(exec_check)

        # If execution failed, return early
        if not exec_check.passed:
            return report

        # Layer 2: Data Shape (if DataFrame provided)
        if df is not None:
            shape_report = self.verify_dataframe(
                df,
                min_rows=kwargs.get('min_rows'),
                max_rows=kwargs.get('max_rows'),
                required_columns=kwargs.get('required_columns'),
                no_null_columns=kwargs.get('no_null_columns'),
                check_duplicates=kwargs.get('check_duplicates', False)
            )
            for result in shape_report.results:
                report.add(result)

        # Layer 3: Domain (if value provided)
        if value is not None:
            domain_report = self.verify_financial_value(
                value,
                value_type=value_type,
                typical_range=kwargs.get('typical_range')
            )
            for result in domain_report.results:
                report.add(result)

        return report


# Convenience functions

def verify_pandas_result(result_str: str) -> VerificationResult:
    """Quick verification of pandas execution result."""
    pipeline = VerificationPipeline()
    return pipeline.verify_execution_result(result_str)


def verify_and_get_feedback(
    execution_result: str,
    df: pd.DataFrame = None,
    **kwargs
) -> tuple:
    """
    Run verification and return (passed, feedback_string).

    Useful for agent self-correction loop.
    """
    pipeline = VerificationPipeline()
    report = pipeline.verify_full(execution_result, df, **kwargs)
    return report.passed, report.to_feedback()


def classify_exception(error_string: str) -> Dict[str, Any]:
    """
    Classify an exception and return structured info for learning.

    Returns:
        {
            'error_type': ErrorType,
            'category': ErrorCategory,
            'message': str,
            'recovery_hint': str
        }
    """
    result = ExceptionClassifier.classify(error_string)
    return {
        'error_type': result.error_type,
        'category': result.category,
        'message': result.error_message,
        'recovery_hint': result.recovery_hint
    }
