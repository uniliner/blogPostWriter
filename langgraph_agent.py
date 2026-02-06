"""
LangGraph Agent for Blog Post Writer.

This module defines the LangGraph workflow that orchestrates the blog post writing process.

Key LangGraph Concepts Demonstrated:
1. StateGraph - Graph with state management
2. Nodes - Pure functions that update state
3. Edges - Connections between nodes
4. Conditional Edges - Routing based on state conditions
5. Compiled Graph - Ready-to-execute workflow

Graph Structure:
```
START → create_plan → execute_subtask → should_continue_execution?
                                        ↓
                      ┌─────────────────┼─────────────────┐
                      ↓                 ↓                 ↓
              assess_revision    execute_subtask    synthesize
                      ↓                 ↓                 ↓
              execute_subtask ←─────────┘                 ↓
                                                          ↓
                                                    reflect → should_refine?
                                                              ↓
                                                        ┌──────┴──────┐
                                                        ↓             ↓
                                                      refine         END
                                                        ↓
                                                    reflect
```
"""
from langgraph.graph import StateGraph, END
from typing import Literal
from langgraph_state import BlogWriterState
from langgraph_nodes import (
    create_plan_node,
    execute_subtask_node,
    assess_revision_node,
    synthesize_node,
    reflect_node,
    refine_node
)
from logger_config import get_agent_logger

logger = get_agent_logger()


def should_continue_execution(state: BlogWriterState) -> Literal["revise", "continue", "synthesize"]:
    """
    Conditional edge function that routes after subtask execution.

    Checks if:
    1. Plan revision is needed → route to assess_revision
    2. More subtasks to execute → route back to execute_subtask
    3. All subtasks complete → route to synthesize

    Args:
        state: Current workflow state

    Returns:
        String indicating next node: "revise", "continue", or "synthesize"

    LangGraph Concept:
        Conditional edges use functions that return string literals
        to determine routing based on state conditions.
    """
    # Check if revision is needed
    if state.get("needs_revision", False):
        return "revise"

    # Check if all subtasks are complete
    if state["current_subtask_index"] >= len(state["full_plan"]):
        return "synthesize"

    # Continue with next subtask
    return "continue"


def should_refine(state: BlogWriterState) -> Literal["refine", "end"]:
    """
    Conditional edge function that routes after reflection.

    Checks if:
    1. Execution is complete → route to END
    2. Max iterations reached → route to END
    3. Content is satisfactory → route to END
    4. Content needs refinement → route to refine

    Args:
        state: Current workflow state

    Returns:
        String indicating next node: "refine" or "end"

    LangGraph Concept:
        This demonstrates how to implement loops with termination conditions.
        The reflection-refine cycle continues until satisfied or max iterations.
    """
    # Check if execution is complete
    if state.get("execution_complete", False):
        return "end"

    # Check if there's reflection history
    history = state.get("reflection_history", [])
    if not history:
        return "end"

    # Check latest reflection
    latest = history[-1]
    if latest.get("assessment") == "SATISFACTORY":
        return "end"

    # Check max iterations
    if len(history) >= 3:
        return "end"

    # Continue refinement
    return "refine"


def create_blog_writer_graph() -> StateGraph:
    """
    Construct and compile the Blog Writer LangGraph workflow.

    This function:
    1. Creates a StateGraph with BlogWriterState
    2. Adds all nodes to the graph
    3. Defines edges (normal and conditional)
    4. Compiles the graph for execution

    Returns:
        Compiled StateGraph ready for invocation

    LangGraph Concept:
        The StateGraph automatically handles state updates using the
        reducer rules defined in the TypedDict (add for annotated lists,
        overwrite for regular fields).

    Example:
        >>> graph = create_blog_writer_graph()
        >>> result = graph.invoke({"topic": "Python decorators"})
    """
    # Create the state graph
    workflow = StateGraph(BlogWriterState)

    # ===== Add Nodes =====
    # Each node is a function that takes state and returns updates
    workflow.add_node("create_plan", create_plan_node)
    workflow.add_node("execute_subtask", execute_subtask_node)
    workflow.add_node("assess_revision", assess_revision_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("refine", refine_node)

    # ===== Define Entry Point =====
    # Start at create_plan node
    workflow.set_entry_point("create_plan")

    # ===== Define Edges =====

    # From create_plan → execute_subtask
    workflow.add_edge("create_plan", "execute_subtask")

    # From execute_subtask → conditional routing
    # Based on: needs_revision flag, current_subtask_index vs plan length
    workflow.add_conditional_edges(
        "execute_subtask",
        should_continue_execution,
        {
            "revise": "assess_revision",
            "continue": "execute_subtask",
            "synthesize": "synthesize"
        }
    )

    # From assess_revision → execute_subtask
    # After assessing revision, continue execution (plan may have been updated)
    workflow.add_edge("assess_revision", "execute_subtask")

    # From synthesize → reflect
    workflow.add_edge("synthesize", "reflect")

    # From reflect → conditional routing
    # Based on: execution_complete flag, assessment, reflection history length
    workflow.add_conditional_edges(
        "reflect",
        should_refine,
        {
            "refine": "refine",
            "end": END
        }
    )

    # From refine → reflect
    # After refinement, reflect again to check quality
    workflow.add_edge("refine", "reflect")

    # ===== Compile Graph =====
    # Compile the graph to prepare it for execution
    compiled_graph = workflow.compile()

    logger.info("LangGraph workflow compiled successfully")
    logger.info("Graph structure: create_plan → execute_subtask ↔ assess_revision → synthesize → reflect ↔ refine → END")

    return compiled_graph


def run_blog_writer(topic: str) -> BlogWriterState:
    """
    Run the blog writer workflow with the given topic.

    This function:
    1. Creates the compiled graph
    2. Initializes the state with the topic
    3. Invokes the graph
    4. Returns the final state

    Args:
        topic: The technical topic to write about

    Returns:
        Final state with all results including final_content

    Example:
        >>> result = run_blog_writer("Python decorators")
        >>> print(result["final_content"])
        # Prints the final blog post
    """
    logger.info("=" * 60)
    logger.info("LANGGRAPH BLOG POST WRITER")
    logger.info("=" * 60)
    logger.info(f"Topic: {topic}")

    # Create the compiled graph
    graph = create_blog_writer_graph()

    # Initialize state with the topic
    initial_state: BlogWriterState = {
        "topic": topic,
        "full_plan": [],
        "completed_subtasks": [],
        "current_subtask_index": 0,
        "subtask_results": [],
        "plan_revisions": [],
        "original_plan": [],
        "revision_count": 0,
        "synthesized_content": "",
        "reflection_history": [],
        "final_content": "",
        "execution_complete": False,
        "needs_revision": False,
        "obstacle_detected": False,
        "obstacle_info": ""
    }

    # Invoke the graph
    # LangGraph will execute nodes according to the graph structure
    final_state = graph.invoke(initial_state)

    logger.info("=" * 60)
    logger.info("WORKFLOW COMPLETE")
    logger.info("=" * 60)

    return final_state
