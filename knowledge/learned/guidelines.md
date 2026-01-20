# Learned Guidelines

This file is automatically edited by the agent when it discovers best practices.
Guidelines added here will inform future query handling.

DO NOT EDIT MANUALLY - This file is managed by the self-improving agent.

## Guidelines

### VALIDATION_ERROR: Non-existent Product Query
**Error**: User asked about "Product Z" which doesn't exist in the dataset
**Cause**: Dataset only contains Products A, B, C, and D
**Fix**: Always validate product existence before attempting calculations. Check df['Product'].unique() and inform user of available products when they ask about non-existent ones.

<!-- Agent-learned guidelines will be added below this line -->
<!-- ---LEARNING_MARKER--- -->
