<!-- Source: https://platform.claude.com/docs/en/agent-sdk/cost-tracking | Last updated: 2025-01-24 -->

# Tracking Costs and Usage

Understand and track token usage for billing in the Claude Agent SDK

---

The Claude Agent SDK provides detailed token usage information for each interaction with Claude. This guide explains how to properly track costs and understand usage reporting.

## Understanding Token Usage

When Claude processes requests, it reports token usage at the message level. This usage data is essential for tracking costs and billing users appropriately.

### Key Concepts

1. **Steps**: A step is a single request/response pair between your application and Claude
2. **Messages**: Individual messages within a step (text, tool uses, tool results)
3. **Usage**: Token consumption data attached to assistant messages

## Important Usage Rules

### 1. Same ID = Same Usage

**All messages with the same `id` field report identical usage**. When Claude sends multiple messages in the same turn (e.g., text + tool uses), they share the same message ID and usage data.

### 2. Charge Once Per Step

**You should only charge users once per step**, not for each individual message.

### 3. Result Message Contains Cumulative Usage

The final `result` message contains the total cumulative usage from all steps:

```typescript
const result = await query({
  prompt: "Multi-step task",
  options: { /* ... */ }
});

console.log("Total usage:", result.usage);
console.log("Total cost:", result.usage.total_cost_usd);
```

### 4. Per-Model Usage Breakdown

The result message includes `modelUsage`, which provides authoritative per-model usage data:

```typescript
const result = await query({ prompt: "..." });

for (const [modelName, usage] of Object.entries(result.modelUsage)) {
  console.log(`${modelName}: $${usage.costUSD.toFixed(4)}`);
  console.log(`  Input tokens: ${usage.inputTokens}`);
  console.log(`  Output tokens: ${usage.outputTokens}`);
}
```

## Implementation: Cost Tracking System

```python Python
from claude_agent_sdk import query, AssistantMessage, ResultMessage
from datetime import datetime

class CostTracker:
    def __init__(self):
        self.processed_message_ids = set()
        self.step_usages = []

    async def track_conversation(self, prompt):
        result = None

        async for message in query(prompt=prompt):
            self.process_message(message)
            if isinstance(message, ResultMessage):
                result = message

        return {
            "result": result,
            "step_usages": self.step_usages,
            "total_cost": result.total_cost_usd if result else 0
        }

    def process_message(self, message):
        if not isinstance(message, AssistantMessage) or not hasattr(message, 'usage'):
            return

        message_id = getattr(message, 'id', None)
        if not message_id or message_id in self.processed_message_ids:
            return

        self.processed_message_ids.add(message_id)
        self.step_usages.append({
            "message_id": message_id,
            "timestamp": datetime.now().isoformat(),
            "usage": message.usage,
            "cost_usd": self.calculate_cost(message.usage)
        })

    def calculate_cost(self, usage):
        input_cost = usage.get("input_tokens", 0) * 0.00003
        output_cost = usage.get("output_tokens", 0) * 0.00015
        cache_read_cost = usage.get("cache_read_input_tokens", 0) * 0.0000075
        return input_cost + output_cost + cache_read_cost

# Usage
tracker = CostTracker()
result = await tracker.track_conversation("Analyze and refactor this code")
print(f"Steps processed: {len(result['step_usages'])}")
print(f"Total cost: ${result['total_cost']:.4f}")
```

```typescript TypeScript
class CostTracker {
  private processedMessageIds = new Set<string>();
  private stepUsages: Array<any> = [];

  async trackConversation(prompt: string) {
    const result = await query({
      prompt,
      options: {
        onMessage: (message) => {
          this.processMessage(message);
        }
      }
    });

    return {
      result,
      stepUsages: this.stepUsages,
      totalCost: result.usage?.total_cost_usd || 0
    };
  }

  private processMessage(message: any) {
    if (message.type !== 'assistant' || !message.usage) {
      return;
    }

    if (this.processedMessageIds.has(message.id)) {
      return;
    }

    this.processedMessageIds.add(message.id);
    this.stepUsages.push({
      messageId: message.id,
      timestamp: new Date().toISOString(),
      usage: message.usage,
      costUSD: this.calculateCost(message.usage)
    });
  }

  private calculateCost(usage: any): number {
    const inputCost = usage.input_tokens * 0.00003;
    const outputCost = usage.output_tokens * 0.00015;
    const cacheReadCost = (usage.cache_read_input_tokens || 0) * 0.0000075;
    return inputCost + outputCost + cacheReadCost;
  }
}
```

## Best Practices

1. **Use Message IDs for Deduplication**: Always track processed message IDs to avoid double-charging
2. **Monitor the Result Message**: The final result contains authoritative cumulative usage
3. **Implement Logging**: Log all usage data for auditing and debugging
4. **Handle Failures Gracefully**: Track partial usage even if a conversation fails
5. **Consider Streaming**: For streaming responses, accumulate usage as messages arrive

## Usage Fields Reference

Each usage object contains:

- `input_tokens`: Base input tokens processed
- `output_tokens`: Tokens generated in the response
- `cache_creation_input_tokens`: Tokens used to create cache entries
- `cache_read_input_tokens`: Tokens read from cache
- `service_tier`: The service tier used (e.g., "standard")
- `total_cost_usd`: Total cost in USD (only in result message)

## Related Documentation

- [TypeScript SDK Reference](/docs/en/agent-sdk/typescript)
- [SDK Overview](/docs/en/agent-sdk/overview)
- [SDK Permissions](/docs/en/agent-sdk/permissions)
