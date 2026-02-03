"""Delta: Self-Extensible Agent System

A portable agent core that reasons and plans, paired with a sandboxed
execution runtime that allows the agent to dynamically write, load,
introspect, and execute its own extension code.

Usage:
    python main.py "your goal here"
    python main.py --interactive
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.desktop import DesktopAdapter
from src.core.agent import Agent
from src.core.gemini_client import GeminiClient
from src.extensions.registry import ExtensionRegistry


def get_api_key() -> str:
    """Get Gemini API key from environment or prompt."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        key = input("Enter your Gemini API key: ").strip()
        if not key:
            print("Error: API key required")
            sys.exit(1)
    return key


async def run_goal(agent: Agent, goal: str):
    """Run the agent with a specific goal."""
    result = await agent.run(goal)
    
    print("\n" + "=" * 50)
    if result.success:
        print("✅ SUCCESS")
    else:
        print("❌ FAILED")
    
    print(f"Message: {result.message}")
    print(f"Steps taken: {result.steps_taken}")
    
    if result.extensions_created:
        print(f"Extensions created: {', '.join(result.extensions_created)}")
    
    if result.data:
        print(f"Data: {result.data}")
    
    return result


async def interactive_mode(agent: Agent):
    """Run in interactive mode."""
    print("\n🤖 Delta Agent - Interactive Mode")
    print("Commands:")
    print("  goal <description>  - Run agent with a goal")
    print("  list                - List all extensions")
    print("  show <name>         - Show extension source code")
    print("  run <name>          - Execute an extension")
    print("  quit                - Exit")
    print()
    
    while True:
        try:
            user_input = input("Delta> ").strip()
            if not user_input:
                continue
            
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            
            if cmd in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            
            elif cmd == "goal":
                if not arg:
                    print("Usage: goal <description>")
                    continue
                await run_goal(agent, arg)
            
            elif cmd == "list":
                extensions = await agent.list_extensions()
                if not extensions:
                    print("No extensions registered.")
                else:
                    print("\nExtensions:")
                    for ext in extensions:
                        print(f"  - {ext['name']} v{ext['version']}")
                        print(f"    {ext['description']}")
                        print(f"    Capabilities: {', '.join(ext['capabilities'])}")
                        print(f"    Executions: {ext['executions']}")
                print()
            
            elif cmd == "show":
                if not arg:
                    print("Usage: show <extension_name>")
                    continue
                source = await agent.get_extension_source(arg)
                if source:
                    print(f"\n--- {arg} ---")
                    print(source)
                    print("---")
                else:
                    print(f"Extension not found: {arg}")
            
            elif cmd == "run":
                if not arg:
                    print("Usage: run <extension_name>")
                    continue
                result = await agent.execute_extension(arg)
                print(f"Success: {result['success']}")
                if result['success']:
                    print(f"Result: {result['value']}")
                    print(f"Time: {result['execution_time_ms']:.2f}ms")
                else:
                    print(f"Error: {result['error']}")
            
            else:
                # Treat as a goal if not a command
                await run_goal(agent, user_input)
            
        except KeyboardInterrupt:
            print("\nInterrupted. Type 'quit' to exit.")
        except Exception as e:
            print(f"Error: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Delta: Self-Extensible Agent System"
    )
    parser.add_argument(
        "goal",
        nargs="?",
        help="Goal for the agent to accomplish"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Directory for data storage"
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = get_api_key()
    
    # Set up components
    data_dir = Path(args.data_dir).resolve()
    
    print(f"📁 Data directory: {data_dir}")
    
    # Create adapter
    adapter = DesktopAdapter(
        api_key=api_key,
        working_directory=Path.cwd(),
        data_directory=data_dir
    )
    await adapter.initialize()
    
    # Create Gemini client
    gemini = GeminiClient(api_key)
    
    # Create extension registry
    registry = ExtensionRegistry(data_dir / "extensions.db")
    
    # Create agent
    agent = Agent(adapter, gemini, registry)
    
    try:
        if args.interactive or not args.goal:
            await interactive_mode(agent)
        else:
            await run_goal(agent, args.goal)
    finally:
        await adapter.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
