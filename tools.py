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
    Saves content to a file
    """
    try:
        with open(f"output/{filename}", 'w') as f:
            f.write(content)
        return {"status": "success", "message": f"Saved to {filename}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Tool registry for the agent
TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information on a given topic. Returns relevant articles and snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_draft",
        "description": "Save content to a markdown file",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to save"
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to save to (default: draft.md)"
                }
            },
            "required": ["content"]
        }
    }
]

def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Any:
    """
    Execute a tool by name with given input
    """
    if tool_name == "web_search":
        return web_search(tool_input["query"])
    elif tool_name == "save_draft":
        return save_draft(tool_input["content"], tool_input.get("filename", "draft.md"))
    else:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
