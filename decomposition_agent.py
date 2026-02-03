import anthropic
import os
from typing import List, Dict, Any
import re
from tools import TOOLS, execute_tool
from prompts import (
    DECOMPOSITION_PLANNING_PROMPT,
    SUBTASK_EXECUTION_PROMPT,
    SYNTHESIS_PROMPT,
    REFLECTION_PROMPT,
    REFINEMENT_PROMPT,
    PLAN_REVISION_PROMPT,
    get_planning_prompt
)


class DecompositionAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.full_plan = []
        self.completed_subtasks = []
        self.subtask_results = []
        # Action Item 12: Plan revision tracking
        self.plan_revisions = []  # Track plan revision history
        self.original_plan = []  # Keep copy of original plan
        self.revision_count = 0
    
    def create_plan(self, topic: str) -> List[str]:
        """
        Phase 1: Create a decomposed task plan
        """
        print(f"\n{'='*60}")
        print("PHASE 1: TASK DECOMPOSITION - CREATING PLAN")
        print(f"{'='*60}\n")

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=DECOMPOSITION_PLANNING_PROMPT,
            messages=[
                {"role": "user", "content": get_planning_prompt(topic)}
            ]
        )

        plan_text = response.content[0].text
        print(f"📋 GENERATED PLAN:\n{plan_text}\n")

        # Parse subtasks from the response
        subtasks = self._parse_subtasks(plan_text)
        self.full_plan = subtasks
        self.original_plan = subtasks.copy()  # Store original for revision tracking

        print(f"✅ Plan created with {len(subtasks)} subtasks\n")
        return subtasks
    
    def _parse_subtasks(self, plan_text: str) -> List[str]:
        """
        Extract subtasks from the plan text
        """
        # Look for patterns like "SUBTASK 1:", "1.", "Step 1:", etc.
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

    # Action Item 12: Plan revision methods
    def _detect_obstacle(self, subtask_output: str, tool_results: List[str]) -> Dict[str, Any]:
        """
        Detect if an obstacle was encountered during subtask execution.

        Returns dict with keys:
        - 'obstacle_detected': bool
        - 'obstacle_type': str (e.g., 'tool_failure', 'insufficient_info', 'contradictory_info')
        - 'obstacle_info': str describing the obstacle
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

    def _assess_plan_revision_needed(self, obstacle_info: str, topic: str) -> Dict[str, Any]:
        """
        Assess whether plan revision is needed based on encountered obstacle.

        Returns dict with assessment result and decision.
        """
        print(f"\n{'='*60}")
        print("🔄 ASSESSING PLAN REVISION NEED")
        print(f"{'='*60}\n")

        # Format context for the revision prompt
        full_plan_text = "\n".join([
            f"{i+1}. {task}" for i, task in enumerate(self.full_plan)
        ])

        completed_text = "\n".join([
            f"✓ {task}" for task in self.completed_subtasks
        ]) if self.completed_subtasks else "None yet"

        remaining_subtasks = self.full_plan[len(self.completed_subtasks):]
        remaining_text = "\n".join([
            f"{i+1}. {task}" for i, task in enumerate(remaining_subtasks)
        ]) if remaining_subtasks else "None"

        system_prompt = PLAN_REVISION_PROMPT.format(
            original_task=f"Write a technical blog post about: {topic}",
            original_plan=full_plan_text,
            completed_subtasks=completed_text,
            remaining_subtasks=remaining_text,
            obstacle_info=obstacle_info
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": system_prompt}
            ]
        )

        assessment_text = response.content[0].text
        print(f"📋 REVISION ASSESSMENT:\n{assessment_text}\n")

        # Parse the assessment
        assessment = self._parse_revision_assessment(assessment_text)

        return assessment

    def _parse_revision_assessment(self, assessment_text: str) -> Dict[str, Any]:
        """
        Parse the revision assessment response.

        Returns dict with keys: 'assessment', 'reasoning', 'revised_plan', 'revision_notes'
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
                    result['revised_plan'] = self._parse_subtasks(plan_text)

        # Extract revision notes
        if 'REVISION_NOTES:' in assessment_text:
            notes_match = re.search(
                r'REVISION_NOTES:\s*(.*?)$',
                assessment_text, re.DOTALL
            )
            if notes_match:
                result['revision_notes'] = notes_match.group(1).strip()

        return result

    def revise_plan(self, obstacle_info: str, topic: str) -> bool:
        """
        Revise the plan based on encountered obstacle or new information.

        Returns True if plan was revised, False otherwise.
        """
        assessment = self._assess_plan_revision_needed(obstacle_info, topic)

        if assessment['assessment'] == 'KEEP_PLAN':
            print("✅ Plan revision assessment: No changes needed\n")
            return False

        elif assessment['assessment'] == 'ABORT_TASK':
            print("⚠️  Plan revision assessment: Task cannot be completed")
            print(f"   Reason: {assessment['reasoning']}\n")
            return False

        elif assessment['assessment'] == 'REVISE_PLAN':
            print(f"🔄 REVISING PLAN (Revision #{self.revision_count + 1})")
            print(f"   Reason: {assessment['reasoning']}")
            print(f"   Notes: {assessment['revision_notes']}\n")

            old_plan = self.full_plan.copy()

            # Update the plan with completed + revised remaining tasks
            self.full_plan = self.completed_subtasks + assessment['revised_plan']
            self.revision_count += 1

            # Record revision
            revision_record = {
                'revision_number': self.revision_count,
                'old_plan': old_plan,
                'new_plan': self.full_plan.copy(),
                'trigger': obstacle_info,
                'reasoning': assessment['reasoning'],
                'notes': assessment['revision_notes']
            }
            self.plan_revisions.append(revision_record)

            print(f"✅ Plan revised successfully!")
            print(f"   Previous subtasks: {len(old_plan)}")
            print(f"   New subtasks: {len(self.full_plan)}")
            print(f"   Remaining: {len(self.full_plan) - len(self.completed_subtasks)}\n")

            return True

        return False

    def get_plan_revision_summary(self) -> str:
        """
        Get a summary of all plan revisions made during execution.
        """
        if not self.plan_revisions:
            return "No plan revisions were made during execution."

        summary = f"Plan Revision Summary (Total: {self.revision_count} revision(s))\n"
        summary += "=" * 60 + "\n\n"

        for revision in self.plan_revisions:
            summary += f"Revision #{revision['revision_number']}:\n"
            summary += f"  Trigger: {revision['trigger'][:100]}...\n"
            summary += f"  Reasoning: {revision['reasoning'][:150]}...\n"
            summary += f"  Notes: {revision['notes'][:150]}...\n"
            summary += f"  Plan size: {len(revision['old_plan'])} → {len(revision['new_plan'])} subtasks\n"
            summary += "-" * 40 + "\n\n"

        return summary

    def execute_subtask(self, subtask: str, subtask_number: int, topic: str = "") -> Dict[str, Any]:
        """
        Phase 2: Execute a single subtask using ReAct pattern

        Action Item 12: Now includes obstacle detection and plan revision triggers.
        """
        print(f"\n{'='*60}")
        print(f"EXECUTING SUBTASK {subtask_number}/{len(self.full_plan)}")
        print(f"{'='*60}")
        print(f"📌 {subtask}\n")

        # Format the full plan for context
        full_plan_text = "\n".join([
            f"{i+1}. {task}" for i, task in enumerate(self.full_plan)
        ])

        completed_text = "\n".join([
            f"✓ {task}" for task in self.completed_subtasks
        ]) if self.completed_subtasks else "None yet"

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
        tool_results = []  # Track tool results for obstacle detection (Action Item 12)

        while iteration < max_iterations:
            iteration += 1

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )

            # Process response content
            assistant_content = []

            for block in response.content:
                if block.type == "text":
                    print(f"\n💭 {block.text}\n")
                    subtask_output.append(block.text)
                    assistant_content.append(block)

                    # Check if subtask is complete
                    if "SUBTASK COMPLETE" in block.text.upper():
                        print(f"✅ Subtask {subtask_number} completed!\n")

                        # Action Item 12: Check for obstacles before marking as complete
                        obstacle_detection = self._detect_obstacle(
                            "\n".join(subtask_output), tool_results
                        )

                        if obstacle_detection['obstacle_detected']:
                            print(f"⚠️  Obstacle detected: {obstacle_detection['obstacle_type']}")

                            # Try to revise plan if topic is provided
                            if topic:
                                plan_revised = self.revise_plan(
                                    obstacle_detection['obstacle_info'],
                                    topic
                                )

                                if plan_revised:
                                    # Note: Subtask is marked complete, but plan was revised
                                    print("📝 Plan was revised based on this obstacle.\n")

                        self.completed_subtasks.append(subtask)
                        result = {
                            "subtask": subtask,
                            "output": "\n".join(subtask_output),
                            "completed": True,
                            "obstacle_detected": obstacle_detection['obstacle_detected']
                        }
                        self.subtask_results.append(result)
                        return result

                elif block.type == "tool_use":
                    print(f"🔧 TOOL: {block.name}")
                    print(f"   Input: {block.input}")

                    # Execute tool
                    tool_result = execute_tool(block.name, block.input)
                    print(f"   Result: {tool_result}\n")

                    # Track tool result for obstacle detection (Action Item 12)
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
                self.completed_subtasks.append(subtask)
                result = {
                    "subtask": subtask,
                    "output": "\n".join(subtask_output),
                    "completed": True,
                    "obstacle_detected": False
                }
                self.subtask_results.append(result)
                return result

            # Add assistant message if we haven't already
            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})

        # Max iterations reached - consider this an obstacle
        print(f"⚠️  Max iterations reached for subtask {subtask_number}")

        obstacle_info = f"Max iterations reached while executing subtask: {subtask}"

        # Action Item 12: Try to revise plan if topic is provided
        if topic:
            self.revise_plan(obstacle_info, topic)

        result = {
            "subtask": subtask,
            "output": "\n".join(subtask_output),
            "completed": False,
            "obstacle_detected": True
        }
        self.subtask_results.append(result)
        return result
    
    def synthesize_results(self, topic: str) -> str:
        """
        Phase 3: Synthesize all subtask results into final output
        """
        print(f"\n{'='*60}")
        print("PHASE 3: SYNTHESIS - COMBINING RESULTS")
        print(f"{'='*60}\n")

        # Format subtask results
        results_text = ""
        for i, result in enumerate(self.subtask_results):
            results_text += f"\nSUBTASK {i+1}: {result['subtask']}\n"
            results_text += f"OUTPUT:\n{result['output']}\n"
            results_text += "-" * 40 + "\n"

        system_prompt = SYNTHESIS_PROMPT.format(
            original_task=f"Write a technical blog post about: {topic}",
            subtask_results=results_text
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Synthesize all the subtask results into a final, cohesive blog post."}
            ]
        )

        final_output = response.content[0].text
        print(f"✅ Synthesis complete!\n")

        return final_output

    def reflect_and_refine(self, content: str, topic: str, max_iterations: int = 3) -> Dict[str, Any]:
        """
        Phase 4: Self-reflection and refinement (Action Item 11)

        This method implements a self-reflective loop where:
        1. The agent evaluates its own output critically
        2. Identifies potential errors and areas for improvement
        3. Refines the content based on self-critique
        4. Repeats until satisfied or max iterations reached

        Returns:
            Dict containing:
            - 'final_content': The improved blog post
            - 'reflection_history': List of all reflections and improvements
            - 'iterations': Number of refinement cycles performed
        """
        print(f"\n{'='*60}")
        print("PHASE 4: SELF-REFLECTION AND REFINEMENT")
        print(f"{'='*60}\n")

        current_content = content
        reflection_history = []

        for iteration in range(max_iterations):
            print(f"\n--- Reflection Cycle {iteration + 1}/{max_iterations} ---\n")

            # Step 1: Reflect on current content
            print("🔍 Evaluating current output...\n")

            reflection_prompt = REFLECTION_PROMPT.format(
                original_task=f"Write a technical blog post about: {topic}",
                content=current_content
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": reflection_prompt}
                ]
            )

            critique = response.content[0].text
            print(f"📝 CRITIQUE:\n{critique}\n")

            # Record the reflection
            reflection_record = {
                "iteration": iteration + 1,
                "critique": critique,
                "assessment": "NEEDS_IMPROVEMENT" if "NEEDS IMPROVEMENT" in critique.upper() else "SATISFACTORY"
            }

            # Step 2: Check if satisfied
            if "SATISFACTORY" in critique.upper():
                print("✅ Content evaluation: SATISFACTORY")
                print("No further refinement needed.\n")
                reflection_record["action_taken"] = "Accepted - no changes needed"
                reflection_history.append(reflection_record)
                break

            # Step 3: Refine the content
            print("🔧 Refining content based on critique...\n")

            refinement_prompt = REFINEMENT_PROMPT.format(
                original_task=f"Write a technical blog post about: {topic}",
                current_content=current_content,
                feedback=critique
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                messages=[
                    {"role": "user", "content": refinement_prompt}
                ]
            )

            refined_content = response.content[0].text
            current_content = refined_content

            print(f"✅ Refinement {iteration + 1} complete!\n")
            reflection_record["action_taken"] = "Refined based on critique"
            reflection_history.append(reflection_record)

        # If max iterations reached, note it
        if iteration + 1 == max_iterations:
            print(f"ℹ️  Reached maximum refinement iterations ({max_iterations})")
            print("Content may still benefit from further refinement.\n")

        print(f"{'='*60}")
        print("SELF-REFLECTION COMPLETE")
        print(f"{'='*60}\n")

        return {
            "final_content": current_content,
            "reflection_history": reflection_history,
            "iterations": len(reflection_history)
        }
    
    def run(self, topic: str) -> Dict[str, Any]:
        """
        Run the complete decomposition agent workflow with self-reflection

        Action Item 12: Now includes dynamic plan execution with plan revision.

        Returns:
            Dict containing:
            - 'final_content': The improved blog post after reflection
            - 'synthesized_content': The initial synthesized version (before reflection)
            - 'reflection_result': Result from the reflection phase
            - 'reflection_history': List of all reflection cycles
            - 'plan_revisions': List of plan revisions made (Action Item 12)
            - 'original_plan': The initial plan before revisions (Action Item 12)
            - 'final_plan': The plan after all revisions (Action Item 12)
        """
        # Phase 1: Plan
        plan = self.create_plan(topic)

        # Phase 2: Execute each subtask with plan revision support (Action Item 12)
        # Use dynamic iteration since plan may change during execution
        subtask_index = 0
        while subtask_index < len(self.full_plan):
            subtask = self.full_plan[subtask_index]
            # Pass topic for plan revision capability
            self.execute_subtask(subtask, subtask_index + 1, topic)

            # Check if plan was revised during execution
            if len(self.full_plan) != len(plan):
                print(f"📝 Plan was revised during execution!")
                print(f"   New total subtasks: {len(self.full_plan)}\n")

            subtask_index += 1

        # Phase 3: Synthesize
        synthesized_output = self.synthesize_results(topic)

        # Phase 4: Self-reflection and refinement (Action Item 11)
        reflection_result = self.reflect_and_refine(synthesized_output, topic)

        # Return comprehensive result
        return {
            "final_content": reflection_result["final_content"],
            "synthesized_content": synthesized_output,
            "reflection_result": reflection_result,
            "reflection_history": reflection_result["reflection_history"],
            "iterations": reflection_result["iterations"],
            # Action Item 12: Include plan revision information
            "plan_revisions": self.plan_revisions,
            "original_plan": self.original_plan,
            "final_plan": self.full_plan,
            "revision_count": self.revision_count
        }
