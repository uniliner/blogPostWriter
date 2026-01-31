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
        final_blog_post = agent.run(topic)
        
        # Display final output
        print("\n" + "="*60)
        print("FINAL BLOG POST")
        print("="*60 + "\n")
        print(final_blog_post)
        
        # Save to file
        filename = f"blog_post_{topic.replace(' ', '_')[:30]}.md"
        save_draft(final_blog_post, filename)
        print(f"\n✅ Blog post saved to: {filename}")
        
        # Display summary
        print(f"\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"Total subtasks: {len(agent.full_plan)}")
        print(f"Completed: {len(agent.completed_subtasks)}")
        print(f"\nSubtasks executed:")
        for i, subtask in enumerate(agent.completed_subtasks):
            print(f"  {i+1}. {subtask}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
