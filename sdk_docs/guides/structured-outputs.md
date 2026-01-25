<!-- Source: https://platform.claude.com/docs/en/agent-sdk/structured-outputs | Last updated: 2025-01-24 -->

# Get structured output from agents

Return validated JSON from agent workflows using JSON Schema, Zod, or Pydantic. Get type-safe, structured data after multi-turn tool use.

---

Structured outputs let you define the exact shape of data you want back from an agent. The agent can use any tools it needs to complete the task, and you still get validated JSON matching your schema at the end.

## Quick start

Define a JSON Schema describing the shape of data you want, then pass it to `query()` via the `outputFormat` option (TypeScript) or `output_format` option (Python):

```typescript TypeScript
import { query } from '@anthropic-ai/claude-agent-sdk'

const schema = {
  type: 'object',
  properties: {
    company_name: { type: 'string' },
    founded_year: { type: 'number' },
    headquarters: { type: 'string' }
  },
  required: ['company_name']
}

for await (const message of query({
  prompt: 'Research Anthropic and provide key company information',
  options: {
    outputFormat: {
      type: 'json_schema',
      schema: schema
    }
  }
})) {
  if (message.type === 'result' && message.structured_output) {
    console.log(message.structured_output)
    // { company_name: "Anthropic", founded_year: 2021, headquarters: "San Francisco, CA" }
  }
}
```

```python Python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

schema = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "founded_year": {"type": "number"},
        "headquarters": {"type": "string"}
    },
    "required": ["company_name"]
}

async for message in query(
    prompt="Research Anthropic and provide key company information",
    options=ClaudeAgentOptions(
        output_format={
            "type": "json_schema",
            "schema": schema
        }
    )
):
    if isinstance(message, ResultMessage) and message.structured_output:
        print(message.structured_output)
```

## Type-safe schemas with Zod and Pydantic

Use Zod (TypeScript) or Pydantic (Python) to define your schema and get strongly-typed objects back:

```typescript TypeScript
import { z } from 'zod'

const FeaturePlan = z.object({
  feature_name: z.string(),
  summary: z.string(),
  steps: z.array(z.object({
    step_number: z.number(),
    description: z.string(),
    estimated_complexity: z.enum(['low', 'medium', 'high'])
  })),
  risks: z.array(z.string())
})

type FeaturePlan = z.infer<typeof FeaturePlan>

const schema = z.toJSONSchema(FeaturePlan)

for await (const message of query({
  prompt: 'Plan how to add dark mode support to a React app.',
  options: {
    outputFormat: {
      type: 'json_schema',
      schema: schema
    }
  }
})) {
  if (message.type === 'result' && message.structured_output) {
    const parsed = FeaturePlan.safeParse(message.structured_output)
    if (parsed.success) {
      const plan: FeaturePlan = parsed.data
      console.log(`Feature: ${plan.feature_name}`)
    }
  }
}
```

```python Python
from pydantic import BaseModel

class Step(BaseModel):
    step_number: int
    description: str
    estimated_complexity: str

class FeaturePlan(BaseModel):
    feature_name: str
    summary: str
    steps: list[Step]
    risks: list[str]

async for message in query(
    prompt="Plan how to add dark mode support to a React app.",
    options=ClaudeAgentOptions(
        output_format={
            "type": "json_schema",
            "schema": FeaturePlan.model_json_schema()
        }
    )
):
    if isinstance(message, ResultMessage) and message.structured_output:
        plan = FeaturePlan.model_validate(message.structured_output)
        print(f"Feature: {plan.feature_name}")
```

## Error handling

When an error occurs, the result message has a `subtype` indicating what went wrong:

| Subtype | Meaning |
|---------|---------|
| `success` | Output was generated and validated successfully |
| `error_max_structured_output_retries` | Agent couldn't produce valid output after multiple attempts |

```typescript TypeScript
for await (const msg of query({
  prompt: 'Extract contact info from the document',
  options: {
    outputFormat: {
      type: 'json_schema',
      schema: contactSchema
    }
  }
})) {
  if (msg.type === 'result') {
    if (msg.subtype === 'success' && msg.structured_output) {
      console.log(msg.structured_output)
    } else if (msg.subtype === 'error_max_structured_output_retries') {
      console.error('Could not produce valid output')
    }
  }
}
```

**Tips for avoiding errors:**

- **Keep schemas focused.** Deeply nested schemas with many required fields are harder to satisfy.
- **Match schema to task.** If the task might not have all the information your schema requires, make those fields optional.
- **Use clear prompts.** Ambiguous prompts make it harder for the agent to know what output to produce.

## Related resources

- [JSON Schema documentation](https://json-schema.org/)
- [API Structured Outputs](/docs/en/build-with-claude/structured-outputs)
- [Custom tools](/docs/en/agent-sdk/custom-tools)
