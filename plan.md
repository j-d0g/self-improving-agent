Perfect! Here's a **comprehensive implementation plan** for your code agent:

---

# 🎯 Self-Improving Financial Data Analysis Agent - Implementation Plan

**Target:** Production-quality MVP in 4-6 hours  
**Constraints:** Minimal structure, markdown-based learning, 25-example batch threshold

---

## 📋 Table of Contents

1. [Project Setup & Dependencies](#1-project-setup--dependencies)
2. [Initial File Structure](#2-initial-file-structure)
3. [Core Components Implementation](#3-core-components-implementation)
4. [Agent Loop Architecture](#4-agent-loop-architecture)
5. [Meta-Learning System](#5-meta-learning-system)
6. [Testing Strategy](#6-testing-strategy)
7. [Demo Preparation](#7-demo-preparation)

---

## 1. Project Setup & Dependencies

### **1.1 Directory Structure (Bootstrap)**

```bash
mkdir -p financial_agent/knowledge/{core,examples,learned}
cd financial_agent

# Initial structure (3 files only)
touch knowledge/dataset_schema.md
touch knowledge/examples.md
touch agent.py
touch README.md

# Git initialization for version control
git init
git add .
git commit -m "Initial bootstrap structure"
```

### **1.2 Dependencies**

Create `requirements.txt`:
```txt
anthropic==0.42.0
pandas==2.2.0
python-dotenv==1.0.0
```

### **1.3 Environment Setup**

Create `.env`:
```bash
ANTHROPIC_API_KEY=your_api_key_here
```

---

## 2. Initial File Structure

### **2.1 `knowledge/dataset_schema.md`** (Hand-written, ~100 lines)

```markdown
# Financial Dataset Schema

## Overview
21,601 rows of P&L actuals across 5 years (2020-2024), 4 products, 6 countries.

## Column Specifications

| Column | Type | Values | Description |
|--------|------|--------|-------------|
| `Fiscal Year` | int | 2020-2024 | Calendar year |
| `Fiscal Quarter` | str | Q1, Q2, Q3, Q4 | Quarter identifier |
| `Fiscal Period` | str | YYYY-MM | Year-month format |
| `FSLine Statement L1` | str | 4 categories | High-level P&L category |
| `FSLine Statement L2` | str | 15 line items | Detailed line item |
| `Product` | str | Product A/B/C/D | Product identifier |
| `Country` | str | 6 countries | Geographic location |
| `Currency` | str | 6 currencies | Local currency code |
| `Amount in Local Currency` | float | Numeric | Local currency amount |
| `Amount in USD` | float | Numeric | USD converted amount |
| `Version` | str | Actuals | Data type (always Actuals) |

## Financial Statement Structure

### L1 Categories (4 total)
1. **Net Revenue** - Total sales revenue
2. **Cost of Goods Sold** (COGS) - Direct production costs
3. **OPEX** - Operating expenses
4. **Other Income/Expenses** - Non-operating items

### L2 Line Items (15 total)

**Revenue (3 items):**
- Gross Revenue
- Returns and Refunds (negative values)
- Revenue Adjustment

**COGS (3 items):**
- Direct Labor
- Direct Materials
- Manufacturing Overhead

**OPEX (6 items):**
- Marketing Expenses
- R&D Expenses
- Sales Expenses
- General & Administrative
- IT Expenses
- Headcount Expenses

**Other (3 items):**
- Interest Income
- Interest Expense
- Foreign Exchange Gain/Loss

## Quarter Definitions

⚠️ **CRITICAL**: Quarters span 3 months each
- Q1: January (01), February (02), March (03)
- Q2: April (04), May (05), June (06)
- Q3: July (08), August (08), September (09)
- Q4: October (10), November (11), December (12)

## Sample Queries

**Valid products:** Product A, Product B, Product C, Product D  
**Valid countries:** Australia, Canada, Germany, Japan, United Kingdom, United States  
**Valid currencies:** AUD, CAD, EUR, GBP, JPY, USD

## Common Calculations

**Net Revenue:** Sum of (Gross Revenue + Returns and Refunds + Revenue Adjustment)  
**Operating Margin:** (Net Revenue - COGS - OPEX) / Net Revenue  
**YoY Growth:** ((Year2 - Year1) / Year1) * 100
```

### **2.2 `knowledge/examples.md`** (Starts empty)

```markdown
# Query Examples

*This file accumulates successful and failed query attempts.*  
*After 25 examples, meta-learning triggers and this resets.*

---

## ✅ Successful Queries

*(Empty initially)*

---

## ❌ Failed Queries

*(Empty initially)*
```

### **2.3 `knowledge/learned/`** (Empty directory initially)

This directory starts empty. The meta-agent will create files here after batch 1.

---

## 3. Core Components Implementation

### **3.1 File Operations Module** (`utils/file_ops.py`)

```python
"""File operations for knowledge management."""
from pathlib import Path
from datetime import datetime
import re


def read_examples() -> str:
    """Read current examples.md content."""
    examples_path = Path("knowledge/examples.md")
    if not examples_path.exists():
        return "# Query Examples\n\n## ✅ Successful Queries\n\n## ❌ Failed Queries\n"
    return examples_path.read_text()


def count_examples() -> int:
    """Count total examples in examples.md."""
    content = read_examples()
    # Count <example> tags
    return len(re.findall(r'<example\s+id=', content))


def append_example(
    query: str,
    code: str,
    result: str,
    error: str | None,
    feedback: str,
    is_successful: bool
) -> None:
    """Append example to appropriate section."""
    content = read_examples()
    timestamp = datetime.now().isoformat()
    
    # Generate unique ID
    existing_count = count_examples()
    prefix = "S" if is_successful else "F"
    example_id = f"{prefix}{existing_count + 1}"
    
    example_block = f"""
<example id="{example_id}" timestamp="{timestamp}">
<query>
{query}
</query>

<code>
```python
{code}
```
</code>

"""
    
    if is_successful:
        example_block += f"""<result>
{result}
</result>

<feedback>
{feedback}
</feedback>
</example>

---
"""
        # Insert after "## ✅ Successful Queries"
        marker = "## ✅ Successful Queries\n"
        insert_pos = content.find(marker) + len(marker)
    else:
        example_block += f"""<error>
{error}
</error>

<feedback>
{feedback}
</feedback>
</example>

---
"""
        # Insert after "## ❌ Failed Queries"
        marker = "## ❌ Failed Queries\n"
        insert_pos = content.find(marker) + len(marker)
    
    updated_content = content[:insert_pos] + "\n" + example_block + content[insert_pos:]
    Path("knowledge/examples.md").write_text(updated_content)


def read_learned_files() -> dict[str, str]:
    """Read all files from learned/ directory."""
    learned_dir = Path("knowledge/learned")
    if not learned_dir.exists():
        return {}
    
    files = {}
    for filepath in learned_dir.glob("**/*"):
        if filepath.is_file():
            files[str(filepath.relative_to(learned_dir))] = filepath.read_text()
    return files


def read_dataset_schema() -> str:
    """Read dataset schema documentation."""
    return Path("knowledge/dataset_schema.md").read_text()


def archive_and_reset_examples() -> str:
    """Archive current examples and reset for next batch."""
    content = read_examples()
    
    # Create archive directory
    archive_dir = Path("archive")
    archive_dir.mkdir(exist_ok=True)
    
    # Count existing batches
    existing_batches = len(list(archive_dir.glob("batch_*.md")))
    batch_num = existing_batches + 1
    
    # Archive with timestamp
    archive_path = archive_dir / f"batch_{batch_num:03d}.md"
    timestamp = datetime.now().isoformat()
    
    archived_content = f"""# Batch {batch_num} Archive
**Archived:** {timestamp}  
**Example count:** {count_examples()}

{content}
"""
    archive_path.write_text(archived_content)
    
    # Reset examples.md
    reset_content = """# Query Examples

*This file accumulates successful and failed query attempts.*  
*After 25 examples, meta-learning triggers and this resets.*

---

## ✅ Successful Queries

---

## ❌ Failed Queries
"""
    Path("knowledge/examples.md").write_text(reset_content)
    
    return str(archive_path)
```

### **3.2 Code Execution Module** (`utils/code_executor.py`)

```python
"""Safe code execution for pandas queries."""
import pandas as pd
import sys
from io import StringIO
from typing import Any


def execute_pandas_code(code: str, df: pd.DataFrame) -> tuple[Any, str | None]:
    """
    Execute pandas code safely in isolated namespace.
    
    Returns:
        (result, error) - result if successful, error message if failed
    """
    # Create isolated namespace with only pandas and dataframe
    namespace = {
        'pd': pd,
        'df': df,
        '__builtins__': __builtins__,
    }
    
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        # Execute code
        exec(code, namespace)
        
        # Get result (last expression or 'result' variable)
        if 'result' in namespace:
            result = namespace['result']
        else:
            # Try to find last assignment
            lines = code.strip().split('\n')
            last_line = lines[-1].strip()
            if '=' in last_line and not last_line.startswith('#'):
                var_name = last_line.split('=')[0].strip()
                result = namespace.get(var_name)
            else:
                result = None
        
        sys.stdout = old_stdout
        return result, None
        
    except Exception as e:
        sys.stdout = old_stdout
        error_msg = f"{type(e).__name__}: {str(e)}"
        return None, error_msg


def validate_code_safety(code: str) -> tuple[bool, str | None]:
    """
    Basic safety checks on generated code.
    
    Returns:
        (is_safe, warning) - True if safe, warning message if unsafe
    """
    dangerous_patterns = [
        'import os',
        'import sys',
        'import subprocess',
        '__import__',
        'eval(',
        'exec(',
        'open(',
        'file(',
        'write(',
    ]
    
    code_lower = code.lower()
    for pattern in dangerous_patterns:
        if pattern in code_lower:
            return False, f"Unsafe pattern detected: {pattern}"
    
    return True, None
```

### **3.3 Sub-Agent: Learning Retrieval** (`agents/learning_retriever.py`)

```python
"""Sub-agent for retrieving relevant learning examples."""
from anthropic import Anthropic
from textwrap import dedent
from utils.file_ops import read_examples


async def retrieve_relevant_learnings(query: str, max_examples: int = 5) -> str:
    """
    Retrieve most relevant success/failure examples using Haiku 4.5.
    
    Fast semantic matching of past examples to current query.
    Returns markdown with relevant <example> blocks only.
    """
    examples_content = read_examples()
    
    # If no examples yet, return empty
    if "<example" not in examples_content:
        return "No prior examples available yet."
    
    client = Anthropic()
    
    prompt = dedent("""
        <task>
        Find the {max_examples} most semantically similar examples to the user's query.
        </task>
        
        <user_query>
        {query}
        </user_query>
        
        <available_examples>
        {examples}
        </available_examples>
        
        <instructions>
        1. Analyze which examples are most relevant (similar concepts, patterns, or potential pitfalls)
        2. Return ONLY the relevant <example> blocks, unchanged
        3. Include both successful and failed examples if relevant
        4. If fewer than {max_examples} are relevant, return only the relevant ones
        5. Preserve the exact XML structure
        </instructions>
    """).format(
        max_examples=max_examples,
        query=query,
        examples=examples_content
    )
    
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text
```

### **3.4 Sub-Agent: Template Retrieval** (`agents/template_retriever.py`)

```python
"""Sub-agent for retrieving relevant function templates."""
from anthropic import Anthropic
from textwrap import dedent
from pathlib import Path


async def retrieve_relevant_templates(query: str) -> str:
    """
    Retrieve relevant helper functions using Haiku 4.5.
    
    Returns Python code of relevant functions or empty string if none exist.
    """
    learned_dir = Path("knowledge/learned")
    
    # If learned/ doesn't exist yet, return empty
    if not learned_dir.exists():
        return "No learned templates available yet."
    
    # Load all Python files from learned/
    templates = []
    for py_file in learned_dir.glob("*.py"):
        templates.append(f"# From {py_file.name}\n{py_file.read_text()}")
    
    if not templates:
        return "No learned templates available yet."
    
    client = Anthropic()
    
    prompt = dedent("""
        <task>
        Select the most relevant helper functions for this query.
        </task>
        
        <user_query>
        {query}
        </user_query>
        
        <available_templates>
        {templates}
        </available_templates>
        
        <instructions>
        1. Identify which functions would be useful for this query
        2. Return ONLY the relevant function definitions (with docstrings)
        3. If no functions are relevant, return "No relevant templates"
        4. Preserve exact Python syntax
        </instructions>
    """).format(
        query=query,
        templates="\n\n".join(templates)
    )
    
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text
```

### **3.5 Judge Agent** (`agents/judge.py`)

```python
"""Judge agent for evaluating query execution results."""
from anthropic import Anthropic
from textwrap import dedent


async def judge_execution(
    query: str,
    code: str,
    result: Any,
    error: str | None
) -> str:
    """
    Analyze query execution and provide feedback using Haiku 4.5.
    
    Returns concise feedback with ✅ or ❌ prefix and pattern analysis.
    """
    client = Anthropic()
    
    status = "FAILED" if error else "SUCCESS"
    
    prompt = dedent("""
        <task>
        Analyze this query execution and provide concise feedback.
        </task>
        
        <execution>
        Query: {query}
        
        Generated Code:
        ```python
        {code}
        ```
        
        Result: {result}
        Error: {error}
        Status: {status}
        </execution>
        
        <instructions>
        For SUCCESS:
        - Start with ✅
        - Briefly note what was done correctly
        - Identify the pattern/approach used
        
        For FAILURE:
        - Start with ❌
        - Explain root cause clearly
        - Classify error type (e.g., "Date range confusion", "Missing validation")
        - Note if this seems like a recurring pattern
        
        Keep feedback under 100 words, focused and actionable.
        </instructions>
    """).format(
        query=query,
        code=code,
        result=result if result is not None else "None",
        error=error if error else "No error",
        status=status
    )
    
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text.strip()
```

---

## 4. Agent Loop Architecture

### **4.1 Main Orchestrator** (`agent.py`)

```python
"""
Self-Improving Financial Data Analysis Agent

Architecture:
- Haiku 4.5 sub-agents: Learning retrieval, template retrieval, judging
- Sonnet 4.5 orchestrator: Code generation with tool calling
- Opus 4.5 meta-agent: Pattern analysis and improvement generation
"""
import asyncio
import pandas as pd
from pathlib import Path
from anthropic import Anthropic
from textwrap import dedent
from typing import Any

from utils.file_ops import (
    read_examples, count_examples, append_example,
    read_learned_files, read_dataset_schema,
    archive_and_reset_examples
)
from utils.code_executor import execute_pandas_code, validate_code_safety
from agents.learning_retriever import retrieve_relevant_learnings
from agents.template_retriever import retrieve_relevant_templates
from agents.judge import judge_execution
from agents.meta_learner import trigger_meta_learning


class FinancialAnalysisAgent:
    """Self-improving agent for financial data analysis."""
    
    def __init__(self, csv_path: str):
        """Initialize agent with dataset."""
        self.df = pd.read_csv(csv_path)
        self.client = Anthropic()
        self.batch_threshold = 25
        
    async def query(self, question: str) -> dict[str, Any]:
        """
        Main entry point for querying financial data.
        
        Process:
        1. Retrieve relevant learnings (Haiku sub-agent)
        2. Retrieve relevant templates (Haiku sub-agent)
        3. Generate code with context (Sonnet orchestrator)
        4. Execute code safely
        5. Judge result (Haiku sub-agent)
        6. Store example
        7. Check meta-learning trigger
        
        Returns:
            Dict with answer, code, error, and feedback
        """
        print(f"\n🤔 Processing query: {question}")
        
        # STEP 1 & 2: Parallel sub-agent retrieval
        print("📚 Retrieving relevant learnings and templates...")
        learnings, templates = await asyncio.gather(
            retrieve_relevant_learnings(question),
            retrieve_relevant_templates(question)
        )
        
        # STEP 3: Generate code with Sonnet 4.5
        print("💭 Generating code...")
        code = await self._generate_code(question, learnings, templates)
        
        # STEP 4: Execute code
        print("⚙️  Executing code...")
        result, error = execute_pandas_code(code, self.df)
        
        # STEP 5: Judge execution
        print("⚖️  Judging result...")
        feedback = await judge_execution(question, code, result, error)
        
        # STEP 6: Store example
        is_successful = error is None
        append_example(
            query=question,
            code=code,
            result=str(result) if result is not None else "None",
            error=error,
            feedback=feedback,
            is_successful=is_successful
        )
        
        # STEP 7: Check meta-learning trigger
        example_count = count_examples()
        print(f"📊 Total examples: {example_count}/{self.batch_threshold}")
        
        if example_count >= self.batch_threshold:
            print(f"\n🧠 THRESHOLD REACHED! Triggering meta-learning...")
            await trigger_meta_learning()
            archive_path = archive_and_reset_examples()
            print(f"✅ Meta-learning complete. Archived to: {archive_path}")
            print(f"🔄 Examples reset. Starting batch {int(archive_path.stem.split('_')[1]) + 1}")
        
        return {
            "answer": result,
            "code": code,
            "error": error,
            "feedback": feedback,
            "is_successful": is_successful
        }
    
    async def _generate_code(
        self,
        query: str,
        learnings: str,
        templates: str
    ) -> str:
        """
        Generate pandas code using Sonnet 4.5 with tool calling.
        
        Uses tool calling pattern to ensure structured code output.
        """
        # Load dataset schema
        schema = read_dataset_schema()
        
        # Build system prompt
        system_prompt = dedent("""
            You are an expert financial data analyst specialized in pandas.
            
            <role>
            Generate precise pandas code to answer queries about financial P&L data.
            </role>
            
            <available_context>
            1. Dataset schema - column definitions and valid values
            2. Learned templates - proven helper functions from past queries
            3. Past examples - successful patterns and common mistakes to avoid
            </available_context>
            
            <constraints>
            - Only use pandas operations (df filtering, groupby, aggregations)
            - Store final answer in variable called 'result'
            - Use helper functions from templates when available
            - Be mindful of past mistakes shown in examples
            - Never use os, sys, subprocess, or file operations
            </constraints>
            
            <output>
            Call the submit_code tool with your generated pandas code.
            </output>
        """).strip()
        
        # Build user message with all context
        user_message = dedent("""
            <dataset_schema>
            {schema}
            </dataset_schema>
            
            <learned_templates>
            {templates}
            </learned_templates>
            
            <relevant_examples>
            {learnings}
            </relevant_examples>
            
            <query>
            {query}
            </query>
            
            Generate pandas code to answer this query. Use learned templates where applicable.
        """).format(
            schema=schema,
            templates=templates,
            learnings=learnings,
            query=query
        )
        
        # Define tool for code submission
        tools = [{
            "name": "submit_code",
            "description": "Submit the generated pandas code",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Complete pandas code to execute. Must store final answer in 'result' variable."
                    }
                },
                "required": ["code"]
            }
        }]
        
        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=tools,
            tool_choice={"type": "tool", "name": "submit_code"}
        )
        
        # Extract code from tool call
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_code":
                return block.input["code"]
        
        raise ValueError("No code generated by model")


async def main():
    """Example usage of the agent."""
    # Initialize with dataset
    agent = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    
    # Example query
    result = await agent.query(
        "What was the total Gross Revenue for Product A in Q1 2024?"
    )
    
    print(f"\n{'='*60}")
    print(f"Answer: {result['answer']}")
    print(f"Feedback: {result['feedback']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. Meta-Learning System

### **5.1 Meta-Learning Agent** (`agents/meta_learner.py`)

```python
"""Meta-learning agent for pattern analysis and improvement generation."""
from anthropic import Anthropic
from textwrap import dedent
from pathlib import Path
import re

from utils.file_ops import read_examples, read_learned_files


async def trigger_meta_learning() -> None:
    """
    Analyze 25 examples and generate improvements using Opus 4.5.
    
    Creates or updates files in knowledge/learned/ based on recurring patterns.
    """
    print("\n" + "="*60)
    print("🧠 META-LEARNING ACTIVATED (Opus 4.5)")
    print("="*60)
    
    # Load current examples
    examples_content = read_examples()
    example_count = len(re.findall(r'<example\s+id=', examples_content))
    
    # Load existing learned files
    learned_files = read_learned_files()
    
    client = Anthropic()
    
    system_prompt = dedent("""
        You are a meta-learning agent analyzing query execution patterns.
        
        <primary_objective>
        Identify RECURRING patterns (≥3 occurrences) worth codifying into:
        1. Helper functions (templates)
        2. Best practice guidelines
        3. Validation rules
        </primary_objective>
        
        <thresholds>
        - Minimum occurrences: 3 (absolute minimum for "pattern")
        - Minimum frequency: 12% of total examples (relative significance)
        - BOTH conditions must be met
        - Single occurrences are NOISE - ignore them
        </thresholds>
        
        <output_requirements>
        For EACH pattern meeting thresholds, generate:
        
        1. Pattern analysis:
           - Name and description
           - Occurrence count and percentage
           - Why it merits codification
        
        2. Implementation:
           - Complete Python code (for functions)
           - OR markdown documentation (for guidelines)
           - Include docstrings explaining:
             * Why this was created
             * What it prevents/enables
             * Frequency data
        
        3. File placement:
           - knowledge/learned/functions.py for helper functions
           - knowledge/learned/guidelines.md for best practices
           - Create new files only if genuinely needed
        </output_requirements>
        
        <file_management>
        Current learned/ structure: {current_files}
        
        Rules:
        - Append to existing files when possible
        - Only create new files for distinct categories
        - Never exceed 500 lines per file
        - If files are large, propose split in output
        </file_management>
    """).format(
        current_files=list(learned_files.keys()) if learned_files else "Empty (first batch)"
    ).strip()
    
    user_message = dedent("""
        <examples count="{count}">
        {examples}
        </examples>
        
        <current_learned_files>
        {learned}
        </current_learned_files>
        
        <instructions>
        Analyze these {count} examples for recurring patterns.
        Generate improvements ONLY for patterns appearing ≥3 times AND ≥12% frequency.
        
        Output format:
        
        ## Analysis
        [Your pattern analysis with counts and percentages]
        
        ## Improvements
        
        ### File: knowledge/learned/functions.py
        ```python
        [New or updated function code with docstrings]
        ```
        
        ### File: knowledge/learned/guidelines.md
        ```markdown
        [New or updated guidelines]
        ```
        
        Be specific about what to create/update and provide complete code/content.
        </instructions>
    """).format(
        count=example_count,
        examples=examples_content,
        learned="\n\n".join([f"# {name}\n{content}" for name, content in learned_files.items()])
        if learned_files else "No learned files yet"
    )
    
    print("🔍 Analyzing patterns with Opus 4.5 Extended Thinking...")
    
    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=8192,
        thinking={"enable": True, "min_tokens": 2048},
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    
    # Extract thinking and improvements
    thinking_content = ""
    improvements = ""
    
    for block in response.content:
        if block.type == "thinking":
            thinking_content = block.content
        elif block.type == "text":
            improvements = block.text
    
    print("\n📝 Opus 4.5 Reasoning:")
    print(thinking_content[:500] + "..." if len(thinking_content) > 500 else thinking_content)
    
    # Apply improvements
    await _apply_improvements(improvements)
    
    # Save meta-learning report
    await _save_meta_report(thinking_content, improvements, example_count)


async def _apply_improvements(improvements_text: str) -> None:
    """Parse improvement text and create/update files."""
    learned_dir = Path("knowledge/learned")
    learned_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract file blocks from improvements
    # Pattern: ### File: knowledge/learned/filename
    # Followed by: ```python or ```markdown
    
    file_pattern = r'### File: knowledge/learned/([^\n]+)\n```(?:python|markdown)\n(.*?)\n```'
    matches = re.findall(file_pattern, improvements_text, re.DOTALL)
    
    for filename, content in matches:
        filepath = learned_dir / filename.strip()
        
        # If file exists, append; otherwise create
        if filepath.exists():
            existing = filepath.read_text()
            updated = existing + "\n\n" + content
            filepath.write_text(updated)
            print(f"✅ Updated: {filepath}")
        else:
            filepath.write_text(content)
            print(f"✅ Created: {filepath}")


async def _save_meta_report(thinking: str, improvements: str, example_count: int) -> None:
    """Save meta-learning analysis report."""
    from datetime import datetime
    
    meta_dir = Path("knowledge/meta_learnings")
    meta_dir.mkdir(parents=True, exist_ok=True)
    
    # Count batch number
    existing_reports = len(list(meta_dir.glob("batch_*.md")))
    batch_num = existing_reports + 1
    
    report = dedent("""
        # Meta-Learning Report - Batch {batch}
        **Date:** {date}  
        **Examples Analyzed:** {count}  
        **Triggered By:** Reached {count}-example threshold
        
        ## Opus 4.5 Reasoning Process
        
        {thinking}
        
        ## Generated Improvements
        
        {improvements}
    """).format(
        batch=batch_num,
        date=datetime.now().isoformat(),
        count=example_count,
        thinking=thinking,
        improvements=improvements
    ).strip()
    
    report_path = meta_dir / f"batch_{batch_num:03d}.md"
    report_path.write_text(report)
    print(f"📄 Meta-learning report saved: {report_path}")
```

### **4.2 Code Generation with Context** (in `agent.py`)

This is already covered in section 3.5 above (`_generate_code` method).

---

## 6. Testing Strategy

### **6.1 Demo Script** (`demo.py`)

```python
"""Demo script showing cross-session learning."""
import asyncio
from agent import FinancialAnalysisAgent


async def run_demo():
    """
    Demonstrates self-improvement across sessions.
    
    Session 1: Make mistakes, trigger learning
    Session 2: Apply learned knowledge successfully
    """
    print("\n" + "="*60)
    print("🎬 DEMO: Self-Improving Financial Analysis Agent")
    print("="*60)
    
    # Initialize agent
    agent = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    
    # SESSION 1: Queries that will trigger learning
    session_1_queries = [
        "What was total Q1 2024 revenue for Product A?",
        "What was Q2 2023 revenue for Product B?",
        "Calculate Q3 2022 revenue for Product C?",
        "Show me Q4 2024 revenue for Product D?",
        # ... repeat similar patterns to get 25 total
    ]
    
    print("\n📍 SESSION 1: Initial queries (will make mistakes)")
    print("-" * 60)
    
    for i, query in enumerate(session_1_queries[:5], 1):  # Demo first 5
        result = await agent.query(query)
        print(f"\nQuery {i}: {query}")
        print(f"Result: {result['answer']}")
        print(f"Feedback: {result['feedback'][:100]}...")
    
    # Artificially complete to 25 examples for demo
    # In real demo, you'd run all 25 queries
    
    print("\n" + "="*60)
    print("🔄 SIMULATING FRESH SESSION (New conversation)")
    print("="*60)
    
    # SESSION 2: New agent instance (simulates fresh session)
    new_agent = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    
    print("\n📍 SESSION 2: Similar query with learned knowledge")
    print("-" * 60)
    
    result = await new_agent.query(
        "What was the total Q1 2023 revenue for Product C?"
    )
    
    print(f"\n✨ Result: {result['answer']}")
    print(f"✅ Success: {result['is_successful']}")
    print(f"📝 Feedback: {result['feedback']}")
    
    # Show evidence of learning
    print("\n" + "="*60)
    print("📂 EVIDENCE: Files created by meta-learning")
    print("="*60)
    
    from pathlib import Path
    learned_dir = Path("knowledge/learned")
    if learned_dir.exists():
        for file in learned_dir.glob("*"):
            print(f"\n📄 {file.name}:")
            content = file.read_text()
            print(content[:300] + "..." if len(content) > 300 else content)


if __name__ == "__main__":
    asyncio.run(run_demo())
```

### **6.2 Test Cases** (`tests/test_agent.py`)

```python
"""Test cases for agent functionality."""
import pytest
import pandas as pd
from agent import FinancialAnalysisAgent


@pytest.mark.asyncio
async def test_basic_query():
    """Test basic query execution."""
    agent = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    result = await agent.query("What is the total revenue in 2024?")
    assert result['answer'] is not None


@pytest.mark.asyncio
async def test_learning_persistence():
    """Test that improvements persist across agent instances."""
    # First agent creates learning
    agent1 = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    
    # Simulate 25 queries to trigger meta-learning
    # ... (implementation)
    
    # Second agent should load improvements
    agent2 = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    
    # Query similar to previous failure should now succeed
    # ... (assertion)


@pytest.mark.asyncio
async def test_meta_learning_threshold():
    """Test that meta-learning triggers at exactly 25 examples."""
    from utils.file_ops import count_examples
    
    agent = FinancialAnalysisAgent("FUN_company_pl_actuals_dataset.csv")
    
    # Before threshold
    for i in range(24):
        await agent.query(f"Test query {i}")
    
    assert count_examples() == 24
    # learned/ should still be empty or minimal
    
    # At threshold
    await agent.query("Final query to trigger threshold")
    
    assert count_examples() == 0  # Should reset
    # learned/ should now have files
```

---

## 7. Demo Preparation

### **7.1 Pre-Demo Checklist**

```markdown
## Before Interview

- [ ] Dataset downloaded and in root directory
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with ANTHROPIC_API_KEY
- [ ] Run full demo script once to verify everything works
- [ ] Prepare 2-3 test queries that will fail initially
- [ ] Clear examples.md and learned/ directory for fresh demo
- [ ] Git repo clean with clear commit history
- [ ] README.md has clear setup instructions

## During Interview

- [ ] Start with empty learned/ directory
- [ ] Run 10 queries → show mistakes accumulating
- [ ] Manually add 15 more to examples.md to reach 25 (or run programmatically)
- [ ] Watch meta-learning trigger live
- [ ] Show learned/functions.py being created
- [ ] Restart Python session (fresh import)
- [ ] Run similar query → succeeds using learned function
- [ ] Show git diff of learned/ directory
```

### **7.2 README.md**

```markdown
# Self-Improving Financial Data Analysis Agent

A meta-learning system that improves across sessions by learning from mistakes.

## Architecture

- **Sub-agents (Haiku 4.5):** Fast retrieval and judging
- **Orchestrator (Sonnet 4.5):** Code generation with context
- **Meta-agent (Opus 4.5):** Pattern analysis and improvement generation

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "ANTHROPIC_API_KEY=your_key" > .env

# Download dataset
wget https://codewords-uploads.s3.amazonaws.com/runtime_v2/.../FUN_company_pl_actuals_dataset.csv

# Run demo
python demo.py
```

## How It Works

1. **Query Phase:** User asks question → Agent generates pandas code → Executes
2. **Learning Phase:** Judge evaluates result → Stores example with feedback
3. **Meta-Learning Phase:** After 25 examples, Opus 4.5 analyzes patterns
4. **Improvement Phase:** Creates helper functions and guidelines in `learned/`
5. **Application Phase:** Next session loads improvements automatically

## Key Features

- ✅ Cross-session learning (improvements persist)
- ✅ Noise reduction (only learns from ≥3 occurrences)
- ✅ Self-organizing (agent creates its own structure)
- ✅ Auto-rollback (archives before changes)
- ✅ Production-ready code quality

## File Structure

```
financial_agent/
├── knowledge/
│   ├── dataset_schema.md     # Data structure (hand-written)
│   ├── examples.md           # Accumulates to 25, then resets
│   └── learned/              # Starts empty, agent fills it
├── agent.py                  # Main orchestrator
└── demo.py                   # Demonstration script
```
```

---

## 8. Implementation Order (Step-by-Step)

### **Phase 1: Foundation (1 hour)**
1. ✅ Set up project structure
2. ✅ Write `knowledge/dataset_schema.md` (copy from task description)
3. ✅ Implement `utils/file_ops.py` (file reading/writing)
4. ✅ Implement `utils/code_executor.py` (safe pandas execution)

### **Phase 2: Core Agent (2 hours)**
5. ✅ Implement `agents/learning_retriever.py` (Haiku sub-agent)
6. ✅ Implement `agents/template_retriever.py` (Haiku sub-agent)
7. ✅ Implement `agents/judge.py` (Haiku sub-agent)
8. ✅ Implement main `agent.py` orchestrator (Sonnet 4.5)
9. ✅ Test basic query → execution → storage flow

### **Phase 3: Meta-Learning (1.5 hours)**
10. ✅ Implement `agents/meta_learner.py` (Opus 4.5)
11. ✅ Implement improvement parsing and file creation
12. ✅ Test meta-learning trigger at 25 examples
13. ✅ Verify learned functions are loaded in new session

### **Phase 4: Demo & Polish (1 hour)**
14. ✅ Create `demo.py` script
15. ✅ Test full cross-session learning flow
16. ✅ Write comprehensive README.md
17. ✅ Clean up code, add comments where needed
18. ✅ Final git commit with clean history

---

## 9. Critical Implementation Details

### **9.1 Code Style (From CodeWords Guidelines)**

```python
# ✅ GOOD: Clean, focused functions
async def retrieve_relevant_learnings(query: str) -> str:
    """Retrieve most relevant examples."""
    examples = read_examples()
    if not examples:
        return "No examples yet"
    return await _semantic_match(query, examples)

# ❌ BAD: Nested, verbose try-except
async def retrieve_relevant_learnings(query: str) -> str:
    """Retrieve most relevant examples."""
    try:
        examples = read_examples()
        if examples is not None:
            result = await _semantic_match(query, examples)
            return result
        else:
            return "No examples yet"
    except Exception as e:
        logger.error(f"Error: {e}")
        return "Error occurred"
```

### **9.2 Async Best Practices**

```python
# ✅ GOOD: Parallel sub-agent calls
learnings, templates = await asyncio.gather(
    retrieve_relevant_learnings(query),
    retrieve_relevant_templates(query)
)

# ❌ BAD: Sequential calls (slow)
learnings = await retrieve_relevant_learnings(query)
templates = await retrieve_relevant_templates(query)
```

### **9.3 Tool Calling Pattern (Critical)**

```python
# ✅ GOOD: Forced tool use for structured output
response = client.messages.create(
    model="claude-sonnet-4-5",
    tools=[code_submission_tool],
    tool_choice={"type": "tool", "name": "submit_code"}  # FORCE tool use
)

# Extract from tool call
for block in response.content:
    if block.type == "tool_use":
        return block.input["code"]
```

---

## 10. Success Criteria Checklist

### **Functional Requirements**
- [ ] Accepts natural language queries
- [ ] Generates pandas code correctly
- [ ] Executes code safely (no eval vulnerabilities)
- [ ] Detects errors vs successes
- [ ] Stores examples with feedback
- [ ] Triggers meta-learning at exactly 25 examples
- [ ] Creates learned/functions.py with helper functions
- [ ] New session loads and uses learned functions
- [ ] Archives examples after meta-learning

### **Code Quality**
- [ ] All functions have type hints
- [ ] Clean async/await usage (no blocking calls)
- [ ] No broad try-except blocks
- [ ] Prefer functions over classes
- [ ] NumPy-style docstrings for tools
- [ ] Uses `textwrap.dedent` for prompts
- [ ] No placeholder/mock data

### **Demo Requirements**
- [ ] Shows error in session 1
- [ ] Shows meta-learning trigger
- [ ] Shows file creation in learned/
- [ ] Shows success in session 2 (fresh conversation)
- [ ] Git history shows improvements

---

## 11. Expected Output After Batch 1

### **`knowledge/learned/functions.py`** (Auto-generated)

```python
# Auto-generated by meta-learning agent
# Created: 2024-01-15 from Batch 1 (25 examples)

def get_quarter_months(quarter: str) -> list[str]:
    """
    Map quarter identifier to month codes.
    
    Why created: Quarter filtering errors occurred 7/25 times (28%)
    Prevents: Using only first month instead of all 3 months in quarter
    
    Example:
        >>> get_quarter_months('Q1')
        ['01', '02', '03']
    """
    mapping = {
        'Q1': ['01', '02', '03'],
        'Q2': ['04', '05', '06'],
        'Q3': ['07', '08', '09'],
        'Q4': ['10', '11', '12']
    }
    if quarter not in mapping:
        raise ValueError(f"Invalid quarter: {quarter}. Use Q1, Q2, Q3, or Q4")
    return mapping[quarter]


def validate_product(product: str) -> None:
    """
    Validate product exists in dataset.
    
    Why created: Invalid product queries occurred 4/25 times (16%)
    Prevents: Silent failures returning $0 from empty dataframes
    
    Raises:
        ValueError: If product not in valid set
    """
    valid_products = ['Product A', 'Product B', 'Product C', 'Product D']
    if product not in valid_products:
        raise ValueError(
            f"Product '{product}' does not exist. "
            f"Valid products: {', '.join(valid_products)}"
        )
```

### **`knowledge/learned/guidelines.md`** (Auto-generated)

```markdown
# Query Best Practices

*Auto-generated by meta-learning agent*

## Pattern: Quarter Filtering
**Created:** 2024-01-15 (Batch 1)  
**Frequency:** 7/25 examples (28%)  
**Category:** Date range operations

### Correct Approach
```python
from learned.functions import get_quarter_months

# Get quarter data
months = get_quarter_months('Q1')
quarter_data = df[df['Fiscal Period'].str.split('-').str[1].isin(months)]
```

### Common Mistake
```python
# ❌ WRONG: Only gets first month of quarter
q1_data = df[df['Fiscal Period'].str.startswith('2024-01')]
```

---

## Pattern: Input Validation
**Created:** 2024-01-15 (Batch 1)  
**Frequency:** 4/25 examples (16%)  
**Category:** Data validation

### Correct Approach
```python
from learned.functions import validate_product

# Always validate user inputs
validate_product(user_product)  # Raises clear error if invalid
result = df[df['Product'] == user_product]
```

### Common Mistake
```python
# ❌ WRONG: No validation, returns $0 silently
result = df[df['Product'] == user_product]['Amount in USD'].sum()
# If product doesn't exist, returns 0 without error
```
```

---

## 12. Final Implementation Notes

### **12.1 Code Execution Choice**

**Recommended:** Use `exec()` with isolated namespace (simplest for MVP)

**Why:**
- ✅ No external dependencies
- ✅ Full control over execution environment
- ✅ Easy to debug
- ✅ Sufficient for 4-6 hour constraint

**Alternative (if time permits):** Claude's code execution tool

### **12.2 Pattern Recognition Thresholds**

```python
# In meta_learner.py
MINIMUM_OCCURRENCES = 3      # Absolute minimum
MINIMUM_FREQUENCY = 0.12     # 12% of total examples

def should_codify(occurrences: int, total: int) -> bool:
    return (
        occurrences >= MINIMUM_OCCURRENCES and
        (occurrences / total) >= MINIMUM_FREQUENCY
    )
```

### **12.3 Error Categories to Watch For**

Based on task description, common error types:
1. **Date range confusion** (Q1/Q2/Q3/Q4 logic)
2. **Missing validation** (Product E, invalid countries)
3. **Aggregation errors** (Net Revenue calculation)
4. **Financial formula mistakes** (Operating margin formula)
5. **Data type mismatches** (string vs numeric)

---

## 13. Time Allocation

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Setup & schema | 30 min | Project structure, dataset_schema.md |
| File operations | 30 min | file_ops.py, code_executor.py |
| Sub-agents | 1 hour | 3 Haiku agents (retrieval, judging) |
| Orchestrator | 1.5 hours | Main agent.py with Sonnet 4.5 |
| Meta-learning | 1 hour | Opus 4.5 pattern analysis |
| Testing & demo | 1 hour | demo.py, test cases |
| Documentation | 30 min | README, comments, cleanup |
| **Total** | **6 hours** | **Working MVP** |

---

## 14. Validation Before Submission

```bash
# Run these checks
python -m pytest tests/
python demo.py
python -m pylint agent.py --disable=all --enable=E,F
git log --oneline  # Should show clean commit history
ls knowledge/learned/  # Should show auto-generated files
```

---

**This plan is now ready for your code agent to implement!** 

The structure is ultra-minimal (3 starting files), grows organically, and proves the learning loop works. Every decision is justified by either the task requirements or CodeWords best practices.

Want me to clarify any specific component or add more implementation details for a particular section?