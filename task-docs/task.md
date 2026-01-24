# Agemo Take-Home Task Specification

> This document contains the original task requirements from Agemo for building a self-improving data analysis agent.

**Navigation:** [TASK](TASK.md) | [NOTES](NOTES.md) | [DESIGN](DESIGN.md) | [TRADEOFFS](TRADEOFFS.md) | [BLOG](BLOG.md)

**Next:** [NOTES.md](NOTES.md) — Personal notes and ideas from reading this task

---

## Take-Home Task

*One of the key objectives of this take-home task is to assess your ability to build production-ready AI systems that learn and improve autonomously. We're looking for someone who can transform ambitious ideas into working code. This task is intentionally challenging - we want to see how you approach complex problems, make architectural decisions, and deliver functional results. Feel free to ask questions if you need clarification.*

*We expect the task to be completed in about 4-6 hours. Do not spend more than 8 hours on it. If you choose to spend extra time to add additional features, please flag this in your submission.*

## Overview

At Agemo, we're building CodeWords (Cody) - an AI assistant that helps users build automation workflows. One of our key roadmap items is **self-improvement**: the ability for AI agents to learn from their mistakes, analyze their own execution logs, suggest improvements to their codebase, and automatically evolve to become better over time.

This take-home task focuses on a core challenge in that vision: **building an agent that demonstrates continuous learning across sessions**.

📒 **NOTE: The use of AI tools (including Claude, GPT, etc.) is strongly encouraged.** Document what AI tools you used and how they aided your development process.

---

# The Challenge

Build a **self-improving data analysis chatbot** that:

1. **Analyzes tabular data** (CSV files) through natural language questions
2. **Detects when it makes mistakes** during analysis
3. **Learns from those mistakes** by creating persistent improvements
4. **Demonstrates meta-learning**: The agent gets better **across sessions** - not just within a single conversation

### Example Workflow

**Session 1:**

- User asks: "What was the total Q1 revenue for Product A in 2024?"
- Agent attempts to answer but makes an error (e.g., wrong date filtering logic)
- Agent detects the failure, analyzes what went wrong
- Agent creates a persistent improvement (new helper function, validation rule, or knowledge entry)

**Session 2 (fresh conversation, days later):**

- Different user asks: "What was Q2 revenue for Product B in 2023?"
- Agent successfully applies the learned date filtering logic from Session 1
- No repeat of the previous mistake - the agent has genuinely improved

---

# Key Functional Requirements

### Core Features (Required)

**1. Natural Language → Data Analysis**

- Accept natural language questions about tabular data
- Generate and execute code to answer questions
- Return results in a clear, structured format

**2. Error Detection**

- Detect when analysis produces incorrect or invalid results
- Identify the type of error (logic error, data misunderstanding, edge case, etc.)

**3. Persistent Improvement Mechanism**

- Analyze failures to determine root cause
- Generate improvements (helper functions, validations, corrections, knowledge)
- **Persist improvements across sessions** using external storage
- Apply learned improvements to future queries in **new sessions**

**4. Code Execution**

- Implement safe code execution for generated Python analysis
- **Your choice of approach**: Claude's code execution tool, Python `exec()`, subprocess sandboxing, or any other method
- Justify your decision in the design document

**5. Demo & Documentation**

- Working demo showing cross-session learning
- Clear explanation of your improvement storage and retrieval architecture

### Stretch Goals (Optional)

- **Data Visualization**: Generate charts/graphs for data insights
- **Multi-CSV Support**: Analyze across multiple related datasets
- **Confidence Scoring**: Assess confidence in answers and request validation when uncertain
- **Improvement Versioning**: Track evolution of learned knowledge over time
- **Rollback Mechanism**: Ability to undo ineffective improvements

---

# Technical Considerations

### General Architecture

- **Agent Framework**: How do you structure the agentic loop? (prompt → tool calls → execution → feedback)
- **Code Execution Strategy**: How do you safely execute generated Python code?
    - Claude's [code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)?
    - Python's `exec()` with proper sandboxing?
    - Subprocess isolation?
    - Another approach?
- **Error Detection**: What signals indicate a mistake? How do you classify errors?
- **State Management**: How do you persist learned knowledge across sessions?

### Continuous Learning Design (The Core Challenge)

This is the heart of the task - designing a system where **Session N+1 is measurably better than Session N**.

**Key questions to address:**

**Storage Mechanism**: How do you persist improvements?

- Git commits to a repository?
- External database or knowledge base?
- File-based storage (JSON, Python modules)?
- Vector store for semantic retrieval?
- Redis-like persistent state?
- Something innovative we haven't thought of?

**Improvement Types**: What can the agent learn?

- Helper functions that get added to its toolkit?
- Validation rules that prevent known errors?
- Domain knowledge about data patterns?
- Prompt modifications or system instructions?
- Code templates for common patterns?

**Retrieval & Application**: How are improvements applied in new sessions?

- Loaded automatically at agent initialization?
- Retrieved based on query similarity?
- Applied through modified prompts?
- Injected as available tools?

**Evaluation**: How do you measure whether improvements are effective?

**We encourage innovation here** - surprise us with a clever approach to persistent learning!

### Implementation Stack

**Required:**

- **Python 3.11+**
- **Agentic SDK with tool calling support** - Claude SDK (`anthropic` library) strongly recommended, but you may use any agentic framework (e.g., OpenAI SDK, LangChain, CrewAI, etc.)

**Recommended libraries** (but not required):

- `pandas` for data analysis
- Standard library tools for your chosen approach

**You choose:**

- Code execution method
- Storage mechanism for improvements
- Any additional libraries that support your architecture

---

# Deliverables

### 1. Working Implementation

A Python codebase that demonstrates the self-improving agent. Should include:

- **Main agent code** (agentic loop, tool definitions, improvement logic)
- **Persistent storage mechanism** (whatever approach you chose)
- **Setup instructions** (README with clear steps to run your code)
- **Test scenarios** that demonstrate cross-session learning

**Code quality matters** - we want production-ready code, not hackathon prototypes.

### 2. Demo (Live Preferred or Recorded)

Demonstrate your agent to the team during the onsite interview:

**Live demo preferred** - show us your agent working in real-time

**Recorded walkthrough acceptable** - if you prefer to have a backup or cannot demo live

**What to demonstrate:**

1. **Initial state**: Agent makes a mistake on Question A
2. **Learning**: Agent analyzes the mistake and creates a persistent improvement
3. **Fresh session**: Start a completely new conversation (simulating days later)
4. **Improved state**: Agent handles Question B (similar pattern to A) correctly
5. **Evidence**: Show the stored improvement (file diff, database entry, etc.)

### 3. Design Document

A document (Markdown, Notion, PDF, or similar) explaining:

**Architecture Overview:**

- System diagram showing components and data flow
- How the agentic loop works
- Where improvements are stored and how they're retrieved

**Self-Improvement Mechanism:**

- What triggers improvement creation?
- How are improvements represented? (code? data? prompts?)
- Where are they stored? (justify your choice)
- How are they applied in new sessions?

**Code Execution Strategy:**

- What approach did you choose and why?
- How do you ensure safety/sandboxing?
- Trade-offs of your approach

**Evaluation Strategy:**

- How do you measure improvement effectiveness?
- How would you prevent bad improvements from persisting?

**Production Considerations:**

- What would need to change for a production system?
- Scalability concerns
- Security considerations

**AI Tool Usage:**

- What AI tools did you use and how did they help (or hinder)?
- Which parts did you implement yourself vs. generate?

### 4. Code Repository

- Public or private GitHub repo (share access with us)
- Clean commit history showing your development process
- Clear README with setup and running instructions

**If you use Git for storing improvements**, the commit history becomes part of your deliverable.

---

# Evaluation Criteria

We will assess:

**1. ✅ Execution (40%)** - Does it work? Is the code production-quality?

- Actually demonstrates cross-session learning
- Code is clean, well-structured, and maintainable
- Handles errors gracefully

**2. 🧠 Continuous Learning Design (30%)** - How clever and effective is your meta-learning mechanism?

- Innovation in improvement storage/retrieval
- Thoughtful approach to what can be learned
- Evidence that improvements actually help

**3. 🏗️ System Architecture (15%)** - Is the solution well-designed?

- Clear separation of concerns
- Justified technical choices
- Scalable patterns

**4. 💬 Communication (10%)** - Can you explain your design clearly?

- Design doc is clear and thorough
- Live demo is polished and rehearsed
- You can answer questions about trade-offs

**5. 🚀 Production Readiness (5%)** - How close is this to deployable code?

- Error handling and edge cases
- Logging and observability
- Security considerations

**We care far more about execution than ideas.** We want to see working code that demonstrates genuine learning.

---

# Questions?

This task is designed with intentional ambiguity - part of the challenge is making smart architectural decisions. However, if you have clarifying questions about requirements or constraints, please reach out. We value candidates who ask thoughtful questions.

---

# Sample Dataset

## Dataset: [`FUN_company_pl_actuals_dataset.csv`](https://codewords-uploads.s3.amazonaws.com/runtime_v2/a50dc17a0dda4315bec5a8dadde04cadec29f0f53750422686783d0108765c8c/FUN_company_pl_actuals_dataset.csv)

**Specifications:**

- 📏 **21,601 rows** of financial data
- 📅 **5 years**: 2020-2024
- 📆 **20 quarters** of data
- 📦 **4 products**: Product A, B, C, D
- 🌍 **6 countries**: Australia, Canada, Germany, Japan, United Kingdom, United States
- 💱 **Multi-currency**: AUD, CAD, EUR, GBP, JPY, USD (with USD conversion)

**Columns:**

1. Fiscal Year
2. Fiscal Quarter
3. Fiscal Period (YYYY-MM format)
4. FSLine Statement L1 (High-level category)
5. FSLine Statement L2 (Detailed line item)
6. Product
7. Country
8. Currency
9. Amount in Local Currency
10. Amount in USD
11. Version (all rows are 'Actuals')

**Financial Statement Structure:**

**Level 1 Categories:**

- **Net Revenue**: Total sales and revenue
- **Cost of Goods Sold (COGS)**: Direct costs of production
- **OPEX**: Operating expenses
- **Other Income/Expenses**: Non-operating items

**Level 2 Line Items** (15 detailed categories):

- Revenue: Gross Revenue, Returns and Refunds, Revenue Adjustment
- COGS: Direct Labor, Direct Materials, Manufacturing Overhead
- OPEX: Marketing Expenses, R&D Expenses, Sales Expenses, General & Administrative, IT Expenses, Headcount Expenses
- Other: Interest Income, Interest Expense, Foreign Exchange Gain/Loss

**Sample Data Preview:**

```
Fiscal Year,Quarter,Period,L1,L2,Product,Country,Currency,Local,USD,Version
2020,Q1,2020-01,Net Revenue,Gross Revenue,Product A,Australia,AUD,213437.77,149406.44,Actuals
2020,Q1,2020-01,Net Revenue,Returns and Refunds,Product A,Australia,AUD,-8080.32,-5656.22,Actuals
2020,Q1,2020-01,Cost of Goods Sold,Direct Labor,Product A,Australia,AUD,19182.39,13427.67,Actuals
2020,Q1,2020-01,OPEX,Marketing Expenses,Product A,Australia,AUD,21457.59,15020.31,Actuals
```

---

## Sample Test Questions (All generated by Cody)

Here are example questions at varying difficulty levels. **Note**: We will test your agent with similar but different questions during the demo.

### Easy (Basic Filtering)

**Q:** What was the Gross Revenue for Product A in the United States in Q1 2020?
**Tests:** Basic filtering by product, country, quarter, year, and financial line item

**Q:** How much did the company spend on Marketing Expenses globally in Q2 2023?
**Tests:** Filtering and aggregation across all countries

### Medium (Multi-Step Aggregation)

**Q:** Calculate the total Net Revenue for all products in Q4 2023
**Tests:** Understanding that Net Revenue = Gross Revenue + Returns + Revenue Adjustments (with negative values)

**Q:** What was the year-over-year growth in total OPEX between Q1 2022 and Q1 2023?
**Tests:** Multi-quarter comparison, percentage calculations, aggregating all OPEX subcategories

### Hard (Complex Analysis)

**Q:** Which product had the highest operating margin in Q3 2023?
**Tests:** Calculating Operating Margin = (Revenue - COGS - OPEX) / Revenue, comparing across products

**Q:** What was the foreign exchange impact for Product C across all countries in 2024?
**Tests:** Filtering specific line items, aggregating across quarters/countries, handling negative values

### Very Hard (Edge Cases)

**Q:** Compare the Cost of Goods Sold as a percentage of Gross Revenue between 2020 and 2024 for Product B
**Tests:** Multi-year aggregation, percentage calculations, understanding financial relationships

### Trick Questions (Error Detection)

**Q:** What was the total revenue for Product E in Q1 2023?
**Expected:** "Product E does not exist" (only A, B, C, D exist)

**Q:** Calculate the Employee Headcount in Japan for Q2 2024
**Expected:** "Employee Headcount not in dataset" (only Headcount Expenses exists)
