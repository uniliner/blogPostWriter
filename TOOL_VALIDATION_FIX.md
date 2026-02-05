# Tool Input Validation Fix

## Problem Analysis

### The Error
```
ERROR: Error: 'content'
KeyError: 'content'
```

### Root Cause
When the LLM called `save_draft` with empty input `{}`, the code tried to directly access `tool_input["content"]` without checking if it exists, causing a KeyError.

**Location**: `tools.py` line 69 (before fix)
```python
return save_draft(tool_input["content"], tool_input.get("filename", "draft.md"))
```

### Why This Happened
1. LLM sometimes calls tools with incomplete parameters
2. No validation before accessing dictionary keys
3. No helpful error messages to guide the LLM to correct behavior
4. Tool description wasn't explicit enough about requirements

## Solution Implemented

### 1. Input Validation in `execute_tool()` (Lines 62-99)

**Before**:
```python
elif tool_name == "save_draft":
    return save_draft(tool_input["content"], tool_input.get("filename", "draft.md"))
```

**After**:
```python
elif tool_name == "save_draft":
    # Validate required parameter
    if "content" not in tool_input:
        return {
            "status": "error",
            "message": "Missing required parameter 'content' for save_draft. Please provide the content string to save."
        }

    content = tool_input["content"]

    # Check if content is empty or just whitespace
    if not content or not content.strip():
        return {
            "status": "error",
            "message": "The 'content' parameter for save_draft cannot be empty. Please provide actual content to save."
        }

    filename = tool_input.get("filename", "draft.md")
    return save_draft(content, filename)
```

**Benefits**:
- ✅ Validates parameters before using them
- ✅ Returns clear error messages that guide the LLM
- ✅ Checks for empty/whitespace-only content
- ✅ Allows LLM to self-correct in next iteration

### 2. Enhanced Tool Descriptions (Lines 54-85)

**save_draft tool description before**:
```python
"description": "Save content to a markdown file"
```

**After**:
```python
"description": "Save content to a markdown file in the output directory. IMPORTANT: You must provide the actual content to save as a string. Do not call this tool without content."
```

**Parameter description before**:
```python
"description": "The content to save"
```

**After**:
```python
"description": "REQUIRED: The actual markdown content to save. Must be non-empty string."
```

**Benefits**:
- ✅ More explicit about requirements
- ✅ Emphasizes that content is mandatory
- ✅ Provides clearer guidance to LLM

### 3. Defensive `save_draft()` Function (Lines 15-52)

Added comprehensive validation:
- Checks for None/empty content
- Validates content is a string
- Ensures content is not just whitespace
- Validates filename is provided
- Auto-appends .md extension if missing
- Creates output directory if it doesn't exist

```python
# Validate inputs
if not content:
    return {"status": "error", "message": "Cannot save empty content"}

if not isinstance(content, str):
    return {"status": "error", "message": f"Content must be a string, got {type(content).__name__}"}

if not content.strip():
    return {"status": "error", "message": "Content cannot be empty or just whitespace"}

# ... more validation ...
```

## How It Works Now

### Scenario 1: LLM calls save_draft without content
```
LLM: TOOL: save_draft
     Input: {}
```
**Result**: Returns error message: "Missing required parameter 'content' for save_draft. Please provide the content string to save."
**Next**: LLM sees error, provides content in next call

### Scenario 2: LLM calls save_draft with empty content
```
LLM: TOOL: save_draft
     Input: {"content": ""}
```
**Result**: Returns error message: "The 'content' parameter for save_draft cannot be empty. Please provide actual content to save."
**Next**: LLM sees error, provides actual content

### Scenario 3: LLM calls save_draft correctly
```
LLM: TOOL: save_draft
     Input: {"content": "# My Article\n..."}
```
**Result**: Success - saves to output/draft.md
**Next**: Continues with workflow

## Key Improvements

1. **No More Crashes**: Invalid tool calls return helpful errors instead of crashing
2. **Self-Correcting LLM**: Clear error messages guide the LLM to fix its mistakes
3. **Better Tool Descriptions**: More explicit requirements reduce errors
4. **Multi-Layer Defense**: Validates at both execute_tool and save_draft levels
5. **Defensive Programming**: Handles all edge cases gracefully

## Applied to Both Tools

The same validation pattern was applied to `web_search`:
```python
if "query" not in tool_input:
    return {
        "status": "error",
        "message": "Missing required parameter 'query' for web_search. Please provide a search query string."
    }
```

## Result

Your program will now:
- ✅ Continue running instead of crashing on invalid tool calls
- ✅ Provide clear feedback to the LLM
- ✅ Allow the LLM to self-correct and retry
- ✅ Handle all edge cases gracefully
