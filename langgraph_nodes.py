"""
LangGraph Node Functions for Blog Post Writer.

This module contains all node functions used by the LangGraph workflow.

Each node is a pure function that:
1. Takes the current state as input
2. Reads relevant fields from the state
3. Performs its operation (often calling LLMs)
4. Returns a dict with state updates

Key LangGraph Concept: Nodes don't modify state directly - they return
dictionaries that LangGraph merges into the state using the reducer rules
defined in the TypedDict (add for annotated lists, overwrite for others).
"""
import anthropic
import logging
import os
from typing import Dict, Any
from langgraph_state import BlogWriterState
from langgraph_helpers import (
    parse_subtasks,
    detect_obstacle,
    call_llm_with_retry,
    parse_revision_assessment
)
from prompts import (
    DECOMPOSITION_PLANNING_PROMPT,
    SUBTASK_EXECUTION_PROMPT,
    SYNTHESIS_PROMPT,
    REFLECTION_PROMPT,
    REFINEMENT_PROMPT,
    PLAN_REVISION_PROMPT
)
from tools import TOOLS, execute_tool
from logger_config import get_agent_logger

logger = get_agent_logger()


def create_plan_node(state: BlogWriterState) -> Dict[str, Any]:
    """
    Node 1: Create a decomposed task plan.

    Reads: state["topic"]
    Updates: full_plan, original_plan, current_subtask_index, revision_count

    This node uses the DECOMPOSITION_PLANNING_PROMPT to break down the
    writing task into 6-10 specific, actionable subtasks.

    Args:
        state: Current workflow state

    Returns:
        Dict with state updates

    LangGraph Concept:
        Returns only the fields that should be updated. LangGraph merges
        these into the state using the reducer rules from the TypedDict.
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: TASK DECOMPOSITION - CREATING PLAN")
    logger.info("=" * 60)

    topic = state["topic"]
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Prepare the planning prompt
    user_prompt = f"Create a detailed task plan for writing a technical blog post about: {topic}\n\n"
    user_prompt += "Break this down into specific subtasks that will result in a high-quality, well-researched blog post."

    try:
        # Call LLM with retry logic
        plan_text, _ = call_llm_with_retry(
            client=client,
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system_prompt=DECOMPOSITION_PLANNING_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            context="create_plan_node"
        )

        if plan_text:
            logger.debug(f"GENERATED PLAN:\n{plan_text}")
            # Parse subtasks from the response
            subtasks = parse_subtasks(plan_text)
            logger.info(f"Plan created with {len(subtasks)} subtasks")

            # Return state updates
            return {
                "full_plan": subtasks,
                "original_plan": subtasks.copy(),
                "current_subtask_index": 0,
                "revision_count": 0
            }
        else:
            raise ValueError("Failed to generate plan text from LLM")

    except Exception as e:
        logger.error(f"Error in create_plan_node: {e}")
        raise


def execute_subtask_node(state: BlogWriterState) -> Dict[str, Any]:
    """
    Node 2: Execute a single subtask using ReAct pattern.

    Reads: full_plan, completed_subtasks, current_subtask_index, topic
    Updates: subtask_results, completed_subtasks, current_subtask_index,
             needs_revision, obstacle_detected, obstacle_info

    This node implements ReAct-style execution:
    1. Thought - Reason about the current step
    2. Action - Use tools (web_search, save_draft)
    3. Observation - Review tool results
    4. Repeat until subtask is complete

    Also detects obstacles that may trigger plan revision.

    Args:
        state: Current workflow state

    Returns:
        Dict with state updates
    """
    topic = state["topic"]
    full_plan = state["full_plan"]
    completed_subtasks = state["completed_subtasks"]
    current_index = state["current_subtask_index"]

    if current_index >= len(full_plan):
        # All subtasks complete
        return {
            "execution_complete": True,
            "obstacle_detected": False
        }

    subtask = full_plan[current_index]

    logger.info("=" * 60)
    logger.info(f"EXECUTING SUBTASK {current_index + 1}/{len(full_plan)}")
    logger.info("=" * 60)
    logger.info(f"Subtask: {subtask}")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Format the full plan for context
    full_plan_text = "\n".join([
        f"{i+1}. {task}" for i, task in enumerate(full_plan)
    ])

    completed_text = "\n".join([
        f"✓ {task}" for task in completed_subtasks
    ]) if completed_subtasks else "None yet"

    system_prompt = SUBTASK_EXECUTION_PROMPT.format(
        full_plan=full_plan_text,
        completed_subtasks=completed_text,
        current_subtask=subtask
    )

    messages = [
        {"role": "user", "content": f"Execute this subtask: {subtask}"}
    ]

    iteration = 0
    max_iterations = 10
    subtask_output = []
    tool_results = []  # Track tool results for obstacle detection

    while iteration < max_iterations:
        iteration += 1

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )

            if not hasattr(response, 'content') or not response.content:
                raise ValueError("Response missing content or empty")

            assistant_content = []

            for block in response.content:
                if block.type == "text":
                    logger.debug(block.text)
                    subtask_output.append(block.text)
                    assistant_content.append(block)

                    # Check if subtask is complete
                    if "SUBTASK COMPLETE" in block.text.upper():
                        logger.info(f"Subtask {current_index + 1} completed!")

                        # Check for obstacles
                        obstacle_detection = detect_obstacle(
                            "\n".join(subtask_output), tool_results
                        )

                        result = {
                            "subtask": subtask,
                            "output": "\n".join(subtask_output),
                            "completed": True,
                            "obstacle_detected": obstacle_detection['obstacle_detected']
                        }

                        return {
                            "subtask_results": [result],
                            "completed_subtasks": [subtask],
                            "current_subtask_index": current_index + 1,
                            "needs_revision": obstacle_detection['obstacle_detected'],
                            "obstacle_detected": obstacle_detection['obstacle_detected'],
                            "obstacle_info": obstacle_detection['obstacle_info']
                        }

                elif block.type == "tool_use":
                    logger.debug(f"TOOL: {block.name}")
                    logger.debug(f"Input: {block.input}")

                    # Execute tool
                    tool_result = execute_tool(block.name, block.input)
                    logger.debug(f"Result: {tool_result}")

                    # Track tool result for obstacle detection
                    tool_results.append(str(tool_result))

                    assistant_content.append(block)

                    # Add tool result to messages
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(tool_result)
                            }
                        ]
                    })
                    assistant_content = []

            if response.stop_reason == "end_turn":
                # Subtask finished without explicit "SUBTASK COMPLETE"
                result = {
                    "subtask": subtask,
                    "output": "\n".join(subtask_output),
                    "completed": True,
                    "obstacle_detected": False
                }

                return {
                    "subtask_results": [result],
                    "completed_subtasks": [subtask],
                    "current_subtask_index": current_index + 1,
                    "needs_revision": False,
                    "obstacle_detected": False
                }

            # Add assistant message if we haven't already
            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})

        except Exception as e:
            logger.error(f"Error executing subtask: {e}")
            obstacle_info = f"Error during execution: {str(e)}"
            result = {
                "subtask": subtask,
                "output": "\n".join(subtask_output),
                "completed": False,
                "obstacle_detected": True
            }

            return {
                "subtask_results": [result],
                "completed_subtasks": [subtask],
                "current_subtask_index": current_index + 1,
                "needs_revision": True,
                "obstacle_detected": True,
                "obstacle_info": obstacle_info
            }

    # Max iterations reached
    logger.warning(f"Max iterations reached for subtask {current_index + 1}")
    result = {
        "subtask": subtask,
        "output": "\n".join(subtask_output),
        "completed": False,
        "obstacle_detected": True
    }

    return {
        "subtask_results": [result],
        "completed_subtasks": [subtask],
        "current_subtask_index": current_index + 1,
        "needs_revision": True,
        "obstacle_detected": True,
        "obstacle_info": f"Max iterations reached while executing subtask: {subtask}"
    }


def assess_revision_node(state: BlogWriterState) -> Dict[str, Any]:
    """
    Node 3: Assess whether plan revision is needed after an obstacle.

    Reads: full_plan, completed_subtasks, obstacle_info, topic
    Updates: plan_revisions, full_plan (if revised), revision_count, needs_revision

    This node evaluates whether the remaining plan needs to be revised
    based on obstacles or new information encountered during execution.

    Args:
        state: Current workflow state

    Returns:
        Dict with state updates
    """
    logger.info("=" * 60)
    logger.info("ASSESSING PLAN REVISION NEED")
    logger.info("=" * 60)

    topic = state["topic"]
    full_plan = state["full_plan"]
    completed_subtasks = state["completed_subtasks"]
    obstacle_info = state["obstacle_info"]
    revision_count = state["revision_count"]

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Format context for the revision prompt
    full_plan_text = "\n".join([
        f"{i+1}. {task}" for i, task in enumerate(full_plan)
    ])

    completed_text = "\n".join([
        f"✓ {task}" for task in completed_subtasks
    ]) if completed_subtasks else "None yet"

    remaining_subtasks = full_plan[len(completed_subtasks):]
    remaining_text = "\n".join([
        f"{i+1}. {task}" for i, task in enumerate(remaining_subtasks)
    ]) if remaining_subtasks else "None"

    assessment_prompt = PLAN_REVISION_PROMPT.format(
        original_task=f"Write a technical blog post about: {topic}",
        original_plan=full_plan_text,
        completed_subtasks=completed_text,
        remaining_subtasks=remaining_text,
        obstacle_info=obstacle_info
    )

    try:
        assessment_text, _ = call_llm_with_retry(
            client=client,
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": assessment_prompt}],
            context="assess_revision_node"
        )

        if assessment_text:
            logger.debug(f"REVISION ASSESSMENT:\n{assessment_text}")
            assessment = parse_revision_assessment(assessment_text)

            if assessment['assessment'] == 'KEEP_PLAN':
                logger.info("Plan revision assessment: No changes needed")
                return {
                    "needs_revision": False,
                    "obstacle_detected": False
                }

            elif assessment['assessment'] == 'ABORT_TASK':
                logger.warning("Plan revision assessment: Task cannot be completed")
                logger.warning(f"Reason: {assessment['reasoning']}")
                return {
                    "needs_revision": False,
                    "obstacle_detected": False
                }

            elif assessment['assessment'] == 'REVISE_PLAN':
                logger.info(f"REVISING PLAN (Revision #{revision_count + 1})")
                logger.info(f"Reason: {assessment['reasoning']}")
                logger.info(f"Notes: {assessment['revision_notes']}")

                old_plan = full_plan.copy()
                new_plan = completed_subtasks + assessment['revised_plan']

                # Record revision
                revision_record = {
                    'revision_number': revision_count + 1,
                    'old_plan': old_plan,
                    'new_plan': new_plan.copy(),
                    'trigger': obstacle_info,
                    'reasoning': assessment['reasoning'],
                    'notes': assessment['revision_notes']
                }

                logger.info(f"Plan revised successfully!")
                logger.info(f"Previous subtasks: {len(old_plan)}")
                logger.info(f"New subtasks: {len(new_plan)}")
                logger.info(f"Remaining: {len(new_plan) - len(completed_subtasks)}")

                return {
                    "full_plan": new_plan,
                    "plan_revisions": [revision_record],
                    "revision_count": revision_count + 1,
                    "needs_revision": False,
                    "obstacle_detected": False
                }

    except Exception as e:
        logger.error(f"Error in assess_revision_node: {e}")

    # Default: keep current plan
    logger.warning("Failed to get assessment - keeping current plan")
    return {
        "needs_revision": False,
        "obstacle_detected": False
    }


def synthesize_node(state: BlogWriterState) -> Dict[str, Any]:
    """
    Node 4: Synthesize all subtask results into a final blog post.

    Reads: subtask_results, topic
    Updates: synthesized_content

    This node combines all research findings and written sections
    into a cohesive, well-structured blog post.

    Args:
        state: Current workflow state

    Returns:
        Dict with state updates
    """
    logger.info("=" * 60)
    logger.info("PHASE 3: SYNTHESIS - COMBINING RESULTS")
    logger.info("=" * 60)

    topic = state["topic"]
    subtask_results = state["subtask_results"]

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Format subtask results
    results_text = ""
    for i, result in enumerate(subtask_results):
        results_text += f"\nSUBTASK {i+1}: {result['subtask']}\n"
        results_text += f"OUTPUT:\n{result['output']}\n"
        results_text += "-" * 40 + "\n"

    synthesis_prompt = SYNTHESIS_PROMPT.format(
        original_task=f"Write a technical blog post about: {topic}",
        subtask_results=results_text
    )

    try:
        synthesized_content, _ = call_llm_with_retry(
            client=client,
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system_prompt=synthesis_prompt,
            messages=[
                {"role": "user", "content": "Synthesize all the subtask results into a final, cohesive blog post."}
            ],
            context="synthesize_node"
        )

        if synthesized_content:
            logger.info("Synthesis complete!")
            return {"synthesized_content": synthesized_content}
        else:
            raise ValueError("Failed to synthesize content")

    except Exception as e:
        logger.error(f"Error in synthesize_node: {e}")
        raise


def reflect_node(state: BlogWriterState) -> Dict[str, Any]:
    """
    Node 5: Reflect on the synthesized content and assess quality.

    Reads: synthesized_content, topic, reflection_history
    Updates: reflection_history, final_content (if satisfactory), execution_complete

    This node performs critical self-reflection on the generated content,
    evaluating accuracy, completeness, clarity, structure, and depth.

    Args:
        state: Current workflow state

    Returns:
        Dict with state updates
    """
    logger.info("=" * 60)
    logger.info("PHASE 4: SELF-REFLECTION")
    logger.info("=" * 60)

    topic = state["topic"]
    synthesized_content = state["synthesized_content"]
    reflection_history = state["reflection_history"]

    iteration = len(reflection_history) + 1
    logger.info(f"Reflection Cycle {iteration}/3")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    reflection_prompt = REFLECTION_PROMPT.format(
        original_task=f"Write a technical blog post about: {topic}",
        content=synthesized_content
    )

    try:
        critique, _ = call_llm_with_retry(
            client=client,
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": reflection_prompt}],
            context="reflect_node"
        )

        if not critique:
            logger.warning("Failed to get critique - accepting current content")
            return {
                "final_content": synthesized_content,
                "execution_complete": True
            }

        logger.debug(f"CRITIQUE:\n{critique}")

        # Record the reflection
        assessment = "NEEDS_IMPROVEMENT" if "NEEDS IMPROVEMENT" in critique.upper() else "SATISFACTORY"

        reflection_record = {
            "iteration": iteration,
            "critique": critique,
            "assessment": assessment
        }

        if "SATISFACTORY" in critique.upper():
            logger.info("Content evaluation: SATISFACTORY")
            logger.info("No further refinement needed.")
            reflection_record["action_taken"] = "Accepted - no changes needed"

            return {
                "reflection_history": [reflection_record],
                "final_content": synthesized_content,
                "execution_complete": True
            }

        # Check max iterations
        if iteration >= 3:
            logger.info("Reached maximum refinement iterations (3)")
            reflection_record["action_taken"] = "Max iterations reached - accepting current content"

            return {
                "reflection_history": [reflection_record],
                "final_content": synthesized_content,
                "execution_complete": True
            }

        reflection_record["action_taken"] = "Needs refinement"
        return {
            "reflection_history": [reflection_record],
            "execution_complete": False
        }

    except Exception as e:
        logger.error(f"Error in reflect_node: {e}")
        # Accept current content on error
        return {
            "final_content": synthesized_content,
            "execution_complete": True
        }


def refine_node(state: BlogWriterState) -> Dict[str, Any]:
    """
    Node 6: Refine content based on critical feedback.

    Reads: synthesized_content, reflection_history[-1], topic
    Updates: synthesized_content (with refined version)

    This node revises the blog post to address all issues identified
    in the reflection critique.

    Args:
        state: Current workflow state

    Returns:
        Dict with state updates
    """
    logger.info("=" * 60)
    logger.info("REFINING CONTENT")
    logger.info("=" * 60)

    topic = state["topic"]
    synthesized_content = state["synthesized_content"]
    reflection_history = state["reflection_history"]

    latest_reflection = reflection_history[-1]
    feedback = latest_reflection["critique"]

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    refinement_prompt = REFINEMENT_PROMPT.format(
        original_task=f"Write a technical blog post about: {topic}",
        current_content=synthesized_content,
        feedback=feedback
    )

    try:
        refined_content, _ = call_llm_with_retry(
            client=client,
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": refinement_prompt}],
            context="refine_node"
        )

        if refined_content:
            logger.info("Refinement complete!")
            return {"synthesized_content": refined_content}
        else:
            logger.warning("Failed to refine content - keeping current version")
            return {}

    except Exception as e:
        logger.error(f"Error in refine_node: {e}")
        # Keep current content on error
        return {}
