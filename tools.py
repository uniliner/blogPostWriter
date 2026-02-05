import requests
from typing import Dict, Any
from tavily import TavilyClient

def web_search(query: str) -> Dict[str, Any]:
    """
    performs a web search for the given query using Tavili API
    """
    client = TavilyClient("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")
    return client.search(
        query=query,
        search_depth="advanced"
    )

def save_draft(content: str, filename: str = "draft.md") -> Dict[str, Any]:
    """
    Saves content to a markdown file in the output directory.

    Args:
        content: The markdown content to save
        filename: The filename to save to (default: draft.md)

    Returns:
        Dict with status and message
    """
    # Validate inputs
    if not content:
        return {"status": "error", "message": "Cannot save empty content"}

    if not isinstance(content, str):
        return {"status": "error", "message": f"Content must be a string, got {type(content).__name__}"}

    if not content.strip():
        return {"status": "error", "message": "Content cannot be empty or just whitespace"}

    if not filename:
        return {"status": "error", "message": "Filename cannot be empty"}

    # Ensure filename ends with .md
    if not filename.endswith('.md'):
        filename = f"{filename}.md"

    try:
        # Ensure output directory exists
        import os
        os.makedirs("output", exist_ok=True)

        with open(f"output/{filename}", 'w') as f:
            f.write(content)
        return {"status": "success", "message": f"Successfully saved to output/{filename}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to save file: {str(e)}"}

# Tool registry for the agent
TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information on a given topic. Use this when you need to gather current information, verify facts, or find sources. Returns relevant articles and snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query - be specific and detailed for best results"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_draft",
        "description": "Save content to a markdown file in the output directory. IMPORTANT: You must provide the actual content to save as a string. Do not call this tool without content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "REQUIRED: The actual markdown content to save. Must be non-empty string."
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to save to (default: draft.md). Should end with .md extension."
                }
            },
            "required": ["content"]
        }
    }
]

def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Any:
    """
    Execute a tool by name with given input.

    Validates that all required parameters are present before execution.
    Returns error messages that guide the LLM to correct its tool calls.
    """
    if tool_name == "web_search":
        # Validate required parameter
        if "query" not in tool_input:
            return {
                "status": "error",
                "message": "Missing required parameter 'query' for web_search. Please provide a search query string."
            }
        return web_search(tool_input["query"])

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

    else:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
