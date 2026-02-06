"""
LangGraph State Schema for Blog Post Writer.

This module defines the TypedDict state schema used by the LangGraph workflow.
The state is passed between nodes and accumulates information as the graph executes.

Key LangGraph Concept:
- Annotated[List[X], add] means lists accumulate across nodes
- Regular fields (without annotation) are overwritten on each update
"""
from typing import TypedDict, Annotated, List, Dict, Any
from operator import add


class BlogWriterState(TypedDict):
    """
    State schema for the Blog Post Writer LangGraph workflow.

    This state is passed between all nodes and accumulates results as execution progresses.

    Field Behavior:
    - Annotated[List[X], add]: Lists accumulate (add items across node executions)
    - Regular fields: Overwritten on each update (last write wins)
    """

    # ===== Input =====
    topic: str
    """The technical topic to write about"""

    # ===== Plan Management (accumulate) =====
    full_plan: Annotated[List[str], add]
    """Complete plan with all subtasks (accumulates if updated)"""

    completed_subtasks: Annotated[List[str], add]
    """List of completed subtask descriptions"""

    current_subtask_index: int
    """Index of current subtask being executed (overwritten)"""

    # ===== Results (accumulate) =====
    subtask_results: Annotated[List[Dict[str, Any]], add]
    """Results from each subtask execution. Each entry contains:
    - subtask: str - The subtask description
    - output: str - The output from executing the subtask
    - completed: bool - Whether the subtask completed successfully
    - obstacle_detected: bool - Whether an obstacle was detected
    """

    # ===== Plan Revision (accumulate) =====
    plan_revisions: Annotated[List[Dict[str, Any]], add]
    """History of plan revisions. Each entry contains:
    - revision_number: int - The revision sequence number
    - old_plan: List[str] - The plan before revision
    - new_plan: List[str] - The plan after revision
    - trigger: str - What triggered this revision
    - reasoning: str - Why the revision was needed
    - notes: str - Additional notes about the revision
    """

    original_plan: List[str]
    """The original plan before any revisions (set once, not accumulated)"""

    revision_count: int
    """Number of plan revisions made (overwritten)"""

    # ===== Synthesis (overwrite) =====
    synthesized_content: str
    """The synthesized blog post before refinement (overwritten)"""

    # ===== Reflection (accumulate) =====
    reflection_history: Annotated[List[Dict[str, Any]], add]
    """History of reflection cycles. Each entry contains:
    - iteration: int - The cycle number
    - critique: str - The critical feedback
    - assessment: str - "SATISFACTORY" or "NEEDS_IMPROVEMENT"
    - action_taken: str - What action was taken
    """

    # ===== Output (overwrite) =====
    final_content: str
    """The final refined blog post (overwritten)"""

    # ===== Control Flags (overwrite) =====
    execution_complete: bool
    """Whether the entire workflow is complete"""

    needs_revision: bool
    """Whether a plan revision is needed"""

    obstacle_detected: bool
    """Whether an obstacle was detected during execution"""

    obstacle_info: str
    """Information about an obstacle that was detected"""
