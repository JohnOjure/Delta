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
from src.core.ghost import GhostMode
from dotenv import load_dotenv

load_dotenv()


from src.core.config import ConfigManager, UserConfig

def ensure_config() -> UserConfig:
    """Ensure configuration exists, or run interactive wizard."""
    manager = ConfigManager()
    config = manager.load()
    
    if config and config.api_key:
        return config
        
    print("\n👋 Welcome to Delta Agent! Let's get you set up.\n")
    
    # Interactive Setup Wizard
    print("1. API Authorization")
    print("   We need a Google Gemini API key to power Delta's intelligence.")
    print("   Get one here: https://aistudio.google.com/app/apikey")
    
    while True:
        api_key = input("   Enter your API Key: ").strip()
        if api_key:
            break
        print("   ❌ API Key is required.")
        
    print("\n2. Personalization")
    name = input("   What should I call you? [User]: ").strip() or "User"
    
    print("\n3. Model Selection")
    print("   Select the default AI model to use:")
    print("   1) gemini-3-pro-preview (Latest, most capable)")
    print("   2) gemini-2.0-flash     (Fast, efficient)")
    
    model_choice = input("   Choose [1-2] (default: 1): ").strip()
    model_map = {
        "1": "gemini-3-pro-preview",
        "2": "gemini-2.0-flash"
    }
    model_name = model_map.get(model_choice, "gemini-3-pro-preview")
    
    print("\n4. Safety & Limits")
    limit_input = input("   Daily request limit (default: 100): ").strip()
    try:
        usage_limit = int(limit_input) if limit_input else 100
    except ValueError:
        usage_limit = 100
        
    # Create and save config
    config = UserConfig(
        api_key=api_key,
        user_name=name,
        model_name=model_name,
        usage_limit=usage_limit
    )
    
    manager.save(config)
    print(f"\n✅ Setup complete! Configuration saved to {manager.config_path}")
    print("   You can change these settings later with 'python main.py --config'")
    print("-" * 50 + "\n")
    
    return config


async def run_goal(agent: Agent, goal: str):
    """Run the agent with a specific goal."""
    result = await agent.run(goal)
    
    print("\n" + "=" * 50)
    if result.success:
        print("✅ SUCCESS")
    else:
        print("❌ FAILED")
    
    # Show the actual response/answer if available
    if result.response:
        print(f"\n{result.response}\n")
    else:
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


async def run_agent(args):
    # Ensure configuration
    config = ensure_config()
    
    # Set up components
    data_dir = Path(args.data_dir).resolve()
    
    print(f"📁 Data directory: {data_dir}")
    print(f"👤 User: {config.user_name}")
    print(f"🧠 Model: {config.model_name}")
    
    # Create adapter
    adapter = DesktopAdapter(
        api_key=config.api_key,
        working_directory=Path.cwd(),
        data_directory=data_dir,
        power_mode=config.power_mode
    )
    await adapter.initialize()
    
    # Create Gemini client
    gemini = GeminiClient(config.api_key, model=config.model_name)
    
    # Create extension registry
    registry = ExtensionRegistry(data_dir / "extensions.db")
    
    # Create agent
    agent = Agent(adapter, gemini, registry)
    
    # Initialize Ghost Mode (Autonomy)
    ghost = GhostMode(agent)
    
    try:
        # Start ghost mode in background
        await ghost.start()
        
        if args.interactive or not args.goal:
            await interactive_mode(agent)
        else:
            await run_goal(agent, args.goal)
    except asyncio.CancelledError:
        print("\n\n🛑 Operation cancelled.")
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user.")
    finally:
        await adapter.shutdown()


def print_help():
    """Print the Delta help message."""
    help_text = """
Delta - Autonomous Extension System
===================================

Delta is a self-evolving AI agent capable of planning, reasoning, and creating its own tools (extensions) to solve complex tasks.

Usage:
  delta [command] [options]
  delta "your goal here"

Commands:
  run <goal>           Execute a specific goal (default if no command provided)
  interactive (-i)     Start an interactive session
  server (--web)       Start the Web UI server
  daemon (--daemon)    Start the background daemon process
  help                 Show this help message

Options:
  --data-dir <path>    Specify data directory (default: ~/.delta)
  --reset-memory       Clear agent memory before running
  --debug              Enable debug logging

Examples:
  delta "Research the best python libraries for data analysis"
  delta --web          # Start the UI at http://localhost:8000
  delta --interactive  # Start CLI chat mode
  delta help           # Show this message

For more details, see the README.md or documentation.
"""
    print(help_text)


def main():
    # Check for "help" command before argparse to override default behavior if needed, 
    # though argparse handles -h/--help. "delta help" ends up as goal="help".
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        print_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="Delta: Self-Extensible Agent System",
        add_help=False # We'll handle help manually or via our custom flag if we wanted, but let's keep default -h too.
                       # Actually, keeping default -h is good.
    )
    # Re-enable default help but with our formatter if we wanted, but simplistic is fine.
    # Let's just catch "help" as a positional arg.
    
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
    
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start the Web UI"
    )
    
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Start the background daemon"
    )
    
    # Custom help flag to use our print_help
    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="Show this help message and exit"
    )
    
    args = parser.parse_args()
    
    if args.help:
        print_help()
        sys.exit(0)
    
    # Handle Web UI Launch
    if args.web:
        try:
            import uvicorn
            import webbrowser
            from threading import Timer
            
            url = "http://localhost:8000"
            print(f"🌐 Starting Delta Web UI at {url}...")
            
            # Simple approach: threaded timer to open browser
            Timer(1.5, lambda: webbrowser.open(url)).start()
            
            # Import app directly to avoid re-import issues
            from src.web.server import app
            
            # Run uvicorn synchronously (this starts its own event loop)
            # Binding to 0.0.0.0 for cross-environment accessibility
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
            return
        except ImportError:
            print("❌ Error: Web dependencies not installed.")
            print("Run: pip install fastapi uvicorn websockets")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error starting Web UI: {e}")
            sys.exit(1)
            
    # Handle Daemon Launch
    if args.daemon:
        try:
            from src.daemon.service import run_daemon
            print("👻 Starting Delta background daemon...")
            asyncio.run(run_daemon())
            return
        except Exception as e:
            print(f"❌ Error starting daemon: {e}")
            sys.exit(1)
            
    # Run agent in asyncio event loop
    try:
        asyncio.run(run_agent(args))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

