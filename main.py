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
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
