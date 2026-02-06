"""
Main entry point for LangGraph Blog Post Writer.

This module provides the command-line interface for running the blog post writer
using the LangGraph-based implementation.

Usage:
    python langgraph_main.py

The LangGraph implementation provides:
- Declarative workflow definition
- Better observability and debugging
- Stateful execution with checkpointing support (future enhancement)
- Easier to understand and maintain
"""
import os
import logging
from dotenv import load_dotenv
from langgraph_agent import run_blog_writer
from tools import save_draft
from logger_config import get_main_logger

load_dotenv()

# Get logger
logger = get_main_logger()


def main():
    """Main entry point for the LangGraph Blog Post Writer."""
    logger.info("=" * 60)
    logger.info("TECHNICAL BLOG POST WRITER - LANGGRAPH MODE")
    logger.info("=" * 60)

    topic = input("Enter a technical topic for the blog post: ").strip()

    if not topic:
        logger.error("Please provide a topic")
        return

    # Run the LangGraph workflow
    try:
        result = run_blog_writer(topic)

        # Extract components from result
        final_blog_post = result["final_content"]
        synthesized_content = result["synthesized_content"]
        reflection_history = result["reflection_history"]
        subtask_results = result["subtask_results"]
        plan_revisions = result["plan_revisions"]
        original_plan = result["original_plan"]
        final_plan = result["full_plan"]
        revision_count = result["revision_count"]

        # Display final output
        logger.info("=" * 60)
        logger.info("FINAL BLOG POST (After Self-Reflection)")
        logger.info("=" * 60)
        logger.info(final_blog_post)

        # Save to file
        filename = f"blog_post_{topic.replace(' ', '_')[:30]}.md"
        save_draft(final_blog_post, filename)
        logger.info(f"Blog post saved to: {filename}")

        # Display execution summary
        logger.info("=" * 60)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total subtasks: {len(final_plan)}")
        logger.info(f"Completed: {len(result['completed_subtasks'])}")
        logger.info("Subtasks executed:")
        for i, subtask in enumerate(result["completed_subtasks"]):
            logger.info(f"  {i+1}. {subtask}")

        # Display self-reflection summary
        logger.info("=" * 60)
        logger.info("SELF-REFLECTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Reflection cycles: {len(reflection_history)}")

        if len(reflection_history) == 1 and "SATISFACTORY" in reflection_history[0].get("assessment", ""):
            logger.info("Result: Content was satisfactory on first evaluation - no refinement needed")
        else:
            logger.info("Refinement process:")
            for i, record in enumerate(reflection_history, 1):
                assessment = record.get("assessment", "UNKNOWN")
                action = record.get("action_taken", "No action recorded")
                logger.info(f"  Cycle {i}: {assessment} - {action}")

        # Display plan revision summary
        logger.info("=" * 60)
        logger.info("PLAN REVISION SUMMARY")
        logger.info("=" * 60)

        if revision_count == 0:
            logger.info("No plan revisions were needed during execution.")
            logger.info("The original plan was successfully executed without obstacles.")
        else:
            logger.info(f"Total plan revisions: {revision_count}")
            logger.info(f"Original plan size: {len(original_plan)} subtasks")
            logger.info(f"Final plan size: {len(final_plan)} subtasks")

            logger.info("Revision details:")
            for revision in plan_revisions:
                logger.info(f"Revision #{revision['revision_number']}:")
                logger.info(f"  Trigger: {revision['trigger'][:80]}...")
                logger.info(f"  Reasoning: {revision['reasoning'][:100]}...")
                logger.info(f"  Notes: {revision['notes'][:100]}...")

        logger.info("=" * 60)
        logger.info("LANGGRAPH EXECUTION COMPLETE")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
