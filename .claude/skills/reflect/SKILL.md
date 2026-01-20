---
name: reflect
description: Session retrospective - evaluate what happened, identify friction points, and propose improvements to project artifacts (docs, skills, scripts, hooks).
---

# Reflect

Review the session and identify what to fix in the project.

## What to Evaluate

- Reasoning and decision-making quality
- Tool calls - were they efficient? Redundant? Missing?
- Errors encountered and how they were resolved
- Back-and-forth with user - what needed clarification?
- Time spent on tasks that could be automated or documented
- Mistakes that a simple rule could prevent in future sessions

## Output Format

```
## Reflection

### What Worked Well
- [thing that went smoothly]

### Friction Points
- [thing that was slow, confusing, or error-prone]

### Proposed Improvements

#### Docs
- [specific doc to add/update and why]

#### Skills
- [new skill or skill improvement]

#### Scripts/Hooks
- [automation opportunity]

#### Rules (for CLAUDE.md)
- [rule that would have prevented a friction point, e.g. "Never read entire JSON log files directly"]

#### Other
- [any other improvements]
```

## When to Use

- After completing a significant task
- When a workflow felt inefficient
- Before clearing context to capture learnings
- When the user asks to reflect
