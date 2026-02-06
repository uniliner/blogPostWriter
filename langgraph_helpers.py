"""
Helper functions for LangGraph Blog Post Writer.

This module contains utility functions extracted from the original DecompositionAgent
that are used by LangGraph nodes. These are pure functions that operate on their inputs
and don't depend on agent state.

These helpers include:
- Text parsing functions
- Obstacle detection
- LLM interaction with retry logic
- Response extraction
"""
import anthropic
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from logger_config import get_agent_logger

logger = get_agent_logger()


def parse_subtasks(plan_text: str) -> List[str]:
    """
    Extract subtasks from the plan text.

    Looks for patterns like "SUBTASK 1:", "1.", "Step 1:", etc.

    Args:
        plan_text: The raw plan text from the LLM

    Returns:
        List of subtask descriptions

    Example:
        >>> plan = "SUBTASK 1: Research topic\\nSUBTASK 2: Write draft"
        >>> parse_subtasks(plan)
        ['Research topic', 'Write draft']
    """
    lines = plan_text.strip().split('\n')
    subtasks = []

    for line in lines:
        line = line.strip()
        # Match patterns like "SUBTASK 1:" or "1." or "1:"
        match = re.match(r'^(?:SUBTASK\s+)?(\d+)[\.:]\s*(.+)$', line, re.IGNORECASE)
        if match:
            subtask_description = match.group(2).strip()
            subtasks.append(subtask_description)

    return subtasks


def detect_obstacle(subtask_output: str, tool_results: List[str]) -> Dict[str, Any]:
    """
    Detect if an obstacle was encountered during subtask execution.

    Analyzes the output and tool results for indicators of problems like:
    - Tool failures
    - Insufficient information
    - Contradictory information
    - Approach issues

    Args:
        subtask_output: The output text from the subtask execution
        tool_results: List of tool execution results

    Returns:
        Dict with keys:
        - 'obstacle_detected': bool
        - 'obstacle_type': str (e.g., 'tool_failure', 'insufficient_info')
        - 'obstacle_info': str describing the obstacle

    Example:
        >>> output = "Search failed with error"
        >>> detect_obstacle(output, [])
        {'obstacle_detected': True, 'obstacle_type': 'tool_failure', ...}
    """
    obstacle_indicators = {
        'tool_failure': ['error', 'failed', 'timeout', 'unavailable', 'exception'],
        'insufficient_info': ['not enough information', 'insufficient data', 'cannot find',
                             'no results', 'unable to locate'],
        'contradictory_info': ['contradicts', 'conflicts with', 'inconsistent'],
        'approach_issue': ['better approach', 'more efficient', 'alternative method']
    }

    output_lower = subtask_output.lower()

    for obstacle_type, indicators in obstacle_indicators.items():
        if any(indicator in output_lower for indicator in indicators):
            # Check if tool results also indicate failure
            tool_failures = [r for r in tool_results if 'error' in str(r).lower()]

            return {
                'obstacle_detected': True,
                'obstacle_type': obstacle_type,
                'obstacle_info': f"Detected {obstacle_type} during execution. " +
                               f"Output: {subtask_output[:200]}... " +
                               (f"Tool errors: {tool_failures}" if tool_failures else "")
            }

    return {'obstacle_detected': False, 'obstacle_type': None, 'obstacle_info': ''}


def extract_text_from_response(response, context: str = "API call") -> Tuple[str, bool]:
    """
    Safely extract text content from an Anthropic API response.

    Handles multiple edge cases:
    - Empty content array
    - Max tokens reached (incomplete response)
    - Error responses
    - Non-text content blocks (e.g., tool_use blocks)

    Args:
        response: The Anthropic API response object
        context: Description of where this was called (for logging)

    Returns:
        Tuple of (extracted_text_content, should_retry)
        - extracted_text_content: The combined text from all text blocks
        - should_retry: Whether the caller should retry with higher max_tokens

    Example:
        >>> response = client.messages.create(...)
        >>> text, retry = extract_text_from_response(response, "create_plan")
    """
    try:
        # Check if response exists and has content attribute
        if not hasattr(response, 'content'):
            logger.error(f"Response object missing 'content' attribute in {context}")
            logger.debug(f"Response type: {type(response)}, Response: {response}")
            return "", True  # Retry on missing attribute

        # Check if content is empty or None
        if not response.content or len(response.content) == 0:
            logger.warning(f"Response has empty content array in {context}")

            # Check if this is a max_tokens scenario - retry with higher limit
            if hasattr(response, 'stop_reason') and response.stop_reason == "max_tokens":
                logger.warning(f"Max tokens reached in {context} - will retry with higher limit")
                return "", True  # Signal to retry with higher max_tokens

            return "", True  # Retry on empty content

        # Look for text blocks in the content
        text_blocks = []
        for i, block in enumerate(response.content):
            if hasattr(block, 'type'):
                if block.type == "text":
                    text_blocks.append(block.text)
                elif block.type == "tool_use":
                    # This is expected in some contexts, log for debugging
                    logger.debug(f"Found tool_use block at index {i} in {context}")

        # If we found text blocks, join them
        if text_blocks:
            combined_text = "\n\n".join(text_blocks)
            return combined_text, False  # Success, no retry needed

        # No text blocks found - might be tool_use only, which is valid in some contexts
        logger.warning(f"No text blocks found in response content for {context}")
        logger.debug(f"Content block types: {[block.type for block in response.content if hasattr(block, 'type')]}")

        # Check stop_reason for more context
        if hasattr(response, 'stop_reason'):
            if response.stop_reason == "max_tokens":
                logger.warning(f"Max tokens reached in {context} - will retry with higher limit")
                return "", True  # Retry with higher max_tokens
            elif response.stop_reason == "error":
                logger.warning(f"API returned an error in {context} - will retry")
                return "", True  # Retry on error

        # No text blocks but not an error - return empty and don't retry
        # (caller should handle this case)
        return "", False

    except Exception as e:
        logger.error(f"Exception while extracting text from response in {context}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return "", True  # Retry on exception


def call_llm_with_retry(
    client: anthropic.Anthropic,
    model: str,
    max_tokens: int,
    system_prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    context: str = "LLM call",
    max_retries: int = 3
) -> Tuple[Optional[str], Optional[Any]]:
    """
    Call the LLM with automatic retry logic on token limit errors.

    Doubles max_tokens on each retry if max_tokens is reached.

    Args:
        client: The Anthropic client instance
        model: Model name (e.g., "claude-sonnet-4-20250514")
        max_tokens: Initial max tokens for the response
        system_prompt: Optional system prompt
        messages: List of message dictionaries
        tools: Optional list of tool definitions
        context: Description of where this was called (for logging)
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (extracted_text, response_object)
        - extracted_text: The extracted text content (empty if failed)
        - response_object: The raw API response (for tool_use handling)

    Example:
        >>> text, response = call_llm_with_retry(
        ...     client, "claude-sonnet-4-20250514", 4096,
        ...     system_prompt="You are helpful",
        ...     messages=[{"role": "user", "content": "Hello"}]
        ... )
    """
    base_max_tokens = max_tokens

    for attempt in range(max_retries):
        current_max_tokens = base_max_tokens * (2 ** attempt)

        try:
            # Prepare the API call parameters
            kwargs = {
                "model": model,
                "max_tokens": current_max_tokens
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if messages:
                kwargs["messages"] = messages
            if tools:
                kwargs["tools"] = tools

            response = client.messages.create(**kwargs)

            # Extract text from response
            text_content, should_retry = extract_text_from_response(
                response, f"{context} (attempt {attempt + 1})"
            )

            # If we got text content, return it
            if text_content or not should_retry:
                return text_content, response

            # If we should retry and haven't exhausted retries
            if should_retry and attempt < max_retries - 1:
                logger.info(f"Retrying {context} with increased max_tokens ({current_max_tokens * 2})...")
                continue

            # Last attempt or non-retryable error
            return text_content, response

        except Exception as e:
            logger.error(f"Exception in {context} (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                # Last attempt failed
                raise ValueError(f"Failed to complete {context} after {max_retries} attempts: {e}")
            logger.info(f"Retrying {context}...")

    # Shouldn't reach here, but just in case
    return "", None


def parse_revision_assessment(assessment_text: str) -> Dict[str, Any]:
    """
    Parse the revision assessment response from the LLM.

    Extracts structured information from the assessment text including:
    - ASSESSMENT: KEEP_PLAN / REVISE_PLAN / ABORT_TASK
    - REASONING: Why this assessment was made
    - REVISED_PLAN: New plan if revised
    - REVISION_NOTES: Additional notes

    Args:
        assessment_text: The raw assessment text from the LLM

    Returns:
        Dict with keys: 'assessment', 'reasoning', 'revised_plan', 'revision_notes'

    Example:
        >>> text = "ASSESSMENT: REVISE_PLAN\\nREASONING: Need more research..."
        >>> parse_revision_assessment(text)
        {'assessment': 'REVISE_PLAN', 'reasoning': 'Need more research', ...}
    """
    result = {
        'assessment': 'KEEP_PLAN',
        'reasoning': '',
        'revised_plan': [],
        'revision_notes': ''
    }

    # Extract assessment
    if 'ASSESSMENT:' in assessment_text:
        for line in assessment_text.split('\n'):
            if 'ASSESSMENT:' in line:
                if 'REVISE_PLAN' in line.upper():
                    result['assessment'] = 'REVISE_PLAN'
                elif 'ABORT_TASK' in line.upper():
                    result['assessment'] = 'ABORT_TASK'
                break

    # Extract reasoning
    if 'REASONING:' in assessment_text:
        reasoning_match = re.search(
            r'REASONING:\s*(.*?)(?=REVISED_PLAN:|REVISION_NOTES:|$)',
            assessment_text, re.DOTALL
        )
        if reasoning_match:
            result['reasoning'] = reasoning_match.group(1).strip()

    # Extract revised plan
    if 'REVISED_PLAN:' in assessment_text:
        plan_match = re.search(
            r'REVISED_PLAN:\s*(.*?)(?=REVISION_NOTES:|$)',
            assessment_text, re.DOTALL
        )
        if plan_match:
            plan_text = plan_match.group(1).strip()
            if plan_text and plan_text != "No changes needed":
                result['revised_plan'] = parse_subtasks(plan_text)

    # Extract revision notes
    if 'REVISION_NOTES:' in assessment_text:
        notes_match = re.search(
            r'REVISION_NOTES:\s*(.*?)$',
            assessment_text, re.DOTALL
        )
        if notes_match:
            result['revision_notes'] = notes_match.group(1).strip()

    return result
