import os
from dotenv import load_dotenv
from decomposition_agent import DecompositionAgent
from tools import save_draft

load_dotenv()


def main():
    print("\n" + "="*60)
    print("TECHNICAL BLOG POST WRITER - DECOMPOSITION MODE")
    print("="*60 + "\n")
    
    topic = input("Enter a technical topic for the blog post: ").strip()
    
    if not topic:
        print("Error: Please provide a topic")
        return
    
    # Initialize agent
    agent = DecompositionAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Run the complete workflow
    try:
        result = agent.run(topic)

        # Extract components from result
        final_blog_post = result["final_content"]
        synthesized_content = result["synthesized_content"]
        reflection_history = result["reflection_history"]
        iterations = result["iterations"]
        # Action Item 12: Extract plan revision information
        plan_revisions = result["plan_revisions"]
        original_plan = result["original_plan"]
        final_plan = result["final_plan"]
        revision_count = result["revision_count"]

        # Display final output
        print("\n" + "="*60)
        print("FINAL BLOG POST (After Self-Reflection)")
        print("="*60 + "\n")
        print(final_blog_post)

        # Save to file
        filename = f"blog_post_{topic.replace(' ', '_')[:30]}.md"
        save_draft(final_blog_post, filename)
        print(f"\n✅ Blog post saved to: {filename}")

        # Display execution summary
        print(f"\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"Total subtasks: {len(agent.full_plan)}")
        print(f"Completed: {len(agent.completed_subtasks)}")
        print(f"\nSubtasks executed:")
        for i, subtask in enumerate(agent.completed_subtasks):
            print(f"  {i+1}. {subtask}")

        # Display self-reflection summary (Action Item 11)
        print(f"\n" + "="*60)
        print("SELF-REFLECTION SUMMARY")
        print("="*60)
        print(f"Reflection cycles: {iterations}")

        if iterations == 1 and "SATISFACTORY" in reflection_history[0].get("assessment", ""):
            print("Result: Content was satisfactory on first evaluation - no refinement needed")
        else:
            print("Refinement process:")
            for i, record in enumerate(reflection_history, 1):
                assessment = record.get("assessment", "UNKNOWN")
                action = record.get("action_taken", "No action recorded")
                print(f"  Cycle {i}: {assessment} - {action}")

        # Optionally save synthesized version for comparison
        print(f"\n💡 To compare versions, the synthesized version (before reflection) has been preserved.")
        print(f"   Final content reflects {iterations} reflection cycle(s).")

        # Action Item 12: Display plan revision summary
        print(f"\n" + "="*60)
        print("PLAN REVISION SUMMARY (Action Item 12)")
        print("="*60)

        if revision_count == 0:
            print("No plan revisions were needed during execution.")
            print("The original plan was successfully executed without obstacles.")
        else:
            print(f"Total plan revisions: {revision_count}")
            print(f"Original plan size: {len(original_plan)} subtasks")
            print(f"Final plan size: {len(final_plan)} subtasks")

            print("\nRevision details:")
            for revision in plan_revisions:
                print(f"\n  Revision #{revision['revision_number']}:")
                print(f"    Trigger: {revision['trigger'][:80]}...")
                print(f"    Reasoning: {revision['reasoning'][:100]}...")
                print(f"    Notes: {revision['notes'][:100]}...")

        print(f"\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
