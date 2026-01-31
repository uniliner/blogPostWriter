import anthropic
import os
from typing import List, Dict, Any
import re
from tools import TOOLS, execute_tool
from prompts import (
    DECOMPOSITION_PLANNING_PROMPT,
    SUBTASK_EXECUTION_PROMPT,
    SYNTHESIS_PROMPT,
    get_planning_prompt
)


class DecompositionAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.full_plan = []
        self.completed_subtasks = []
        self.subtask_results = []
    
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
    
    def execute_subtask(self, subtask: str, subtask_number: int) -> Dict[str, Any]:
        """
        Phase 2: Execute a single subtask using ReAct pattern
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
                        self.completed_subtasks.append(subtask)
                        result = {
                            "subtask": subtask,
                            "output": "\n".join(subtask_output),
                            "completed": True
                        }
                        self.subtask_results.append(result)
                        return result
                
                elif block.type == "tool_use":
                    print(f"🔧 TOOL: {block.name}")
                    print(f"   Input: {block.input}")
                    
                    # Execute tool
                    tool_result = execute_tool(block.name, block.input)
                    print(f"   Result: {tool_result}\n")
                    
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
                    "completed": True
                }
                self.subtask_results.append(result)
                return result
            
            # Add assistant message if we haven't already
            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})
        
        # Max iterations reached
        print(f"⚠️  Max iterations reached for subtask {subtask_number}")
        result = {
            "subtask": subtask,
            "output": "\n".join(subtask_output),
            "completed": False
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
    
    def run(self, topic: str) -> str:
        """
        Run the complete decomposition agent workflow
        """
        # Phase 1: Plan
        plan = self.create_plan(topic)
        
        # Phase 2: Execute each subtask
        for i, subtask in enumerate(plan):
            self.execute_subtask(subtask, i + 1)
        
        # Phase 3: Synthesize
        final_output = self.synthesize_results(topic)
        
        return final_output
