# Error Handling and Retry Logic Implementation

## Overview
Implemented robust error handling and retry logic throughout the `decomposition_agent.py` file to handle cases where the LLM API returns responses without the expected 'content' field.

## Key Changes

### 1. Enhanced Response Extraction (`_extract_text_from_response`)
- **Returns**: Tuple of `(extracted_text, should_retry)` instead of just text
- **Handles**:
  - Missing `content` attribute → retry
  - Empty content array → retry
  - Max tokens reached (`stop_reason == "max_tokens"`) → retry with higher limit
  - API errors (`stop_reason == "error"`) → retry
  - Non-text blocks (tool_use only) → returns empty, no retry
  - General exceptions → retry

### 2. Retry Logic Pattern
All API calls now implement the following retry pattern:

```python
max_retries = 3
base_max_tokens = <BASE_LIMIT>

for attempt in range(max_retries):
    max_tokens = base_max_tokens * (2 ** attempt)  # Double each retry

    try:
        response = self.client.messages.create(...)
        text, should_retry = self._extract_text_from_response(...)

        if text:
            return text  # Success!

        if not should_retry or attempt == max_retries - 1:
            break  # Don't retry or last attempt

        logger.info(f"Retrying with increased max_tokens ({max_tokens * 2})...")

    except Exception as e:
        if attempt == max_retries - 1:
            raise  # Re-raise on final attempt
        logger.info("Retrying...")
```

### 3. Updated Methods with Retry Logic

#### `create_plan()` (Line 106-155)
- Base: 2048 tokens
- Retries up to 8192 tokens (2048 → 4096 → 8192)
- Raises `ValueError` if all retries fail

#### `_assess_plan_revision_needed()` (Line 242-285)
- Base: 4096 tokens
- Retries up to 16384 tokens
- Returns default "KEEP_PLAN" assessment if all retries fail (graceful degradation)

#### `execute_subtask()` (Line 444-518)
- Base: 4096 tokens
- Retries up to 16384 tokens
- Triggers plan revision if all retries fail (obstacle detection)

#### `synthesize_results()` (Line 624-661)
- Base: 8192 tokens
- Retries up to 32768 tokens
- Raises `ValueError` if all retries fail

#### `reflect_and_refine()` critique (Line 697-745)
- Base: 4096 tokens
- Retries up to 16384 tokens
- Accepts current content if all retries fail (graceful degradation)

#### `reflect_and_refine()` refinement (Line 771-814)
- Base: 8192 tokens
- Retries up to 32768 tokens
- Keeps current content if all retries fail (graceful degradation)

## Token Limits by Attempt

| Attempt | Multiplier | Plan | Revision | Subtask | Synthesis | Critique | Refinement |
|---------|-----------|------|----------|---------|-----------|----------|------------|
| 1       | 1x        | 2K   | 4K       | 4K      | 8K        | 4K       | 8K         |
| 2       | 2x        | 4K   | 8K       | 8K      | 16K       | 8K       | 16K        |
| 3       | 4x        | 8K   | 16K      | 16K     | 32K       | 16K      | 32K        |

## Recovery Strategies

1. **Increase token limits** - When max_tokens is reached, retry with doubled limit
2. **Retry on transient errors** - Network issues, temporary API errors
3. **Graceful degradation** - Some methods return defaults rather than crashing:
   - Plan revision keeps current plan
   - Reflection accepts current content
4. **Obstacle detection** - Subtask failures trigger plan revision
5. **Detailed logging** - All retries and errors are logged for debugging

## Benefits

✅ **Resilient** - Handles max_tokens, API errors, empty responses
✅ **Self-healing** - Automatically retries with increased limits
✅ **Graceful** - Degrades gracefully when possible instead of crashing
✅ **Transparent** - Logs all retry attempts for visibility
✅ **Adaptive** - Token limits scale based on actual needs

## Testing Recommendations

1. Test with topics that generate very long responses
2. Simulate API failures to verify retry logic
3. Monitor logs for retry patterns
4. Verify graceful degradation works correctly
