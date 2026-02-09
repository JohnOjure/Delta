"""Delta CLI - Command-line interface for Delta agent.

Usage:
    delta ask "question"     - Ask Delta to do something
    delta start              - Start the daemon in background
    delta start --foreground - Run in foreground
    delta stop               - Stop the daemon
    delta status             - Show daemon status
    delta logs               - Show recent logs
    delta config             - Configure Delta
"""

import click
import asyncio
import sys
from pathlib import Path

from src.daemon.manager import ServiceManager


@click.group()
@click.version_option(version="1.0.0", prog_name="Delta")
def cli():
    """Delta - Self-Extensible AI Agent System.
    
    Delta is an AI agent that lives on your system, learns from interactions,
    and can proactively help you with tasks.
    """
    pass


@cli.command()
@click.argument("goal")
def ask(goal: str):
    """Ask Delta to accomplish a goal.
    
    Examples:
        delta ask "What files are in my Downloads?"
        delta ask "Create a script to organize my photos"
    """
    manager = ServiceManager()
    
    if not manager.is_running():
        click.echo("Delta daemon is not running. Starting in foreground mode...")
        # Run goal directly without daemon
        asyncio.run(_run_goal_direct(goal))
    else:
        # Send to daemon via IPC
        click.echo("Sending goal to Delta...")
        result = manager.send_goal(goal)
        
        if result.get("error"):
            click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)
        
        if result.get("success"):
            click.echo(f"\n{result.get('response', result.get('message', 'Done'))}")
        else:
            click.echo(f"Failed: {result.get('message', 'Unknown error')}", err=True)


async def _run_goal_direct(goal: str):
    """Run a goal directly without daemon."""
    from src.core.config import ConfigManager
    from src.adapters.desktop import DesktopAdapter
    from src.core.agent import Agent
    from src.core.gemini_client import GeminiClient
    from src.core.memory import Memory
    from src.extensions.registry import ExtensionRegistry
    
    manager = ConfigManager()
    config = manager.load()
    
    if not config or not config.api_key:
        click.echo("Error: API key not configured.", err=True)
        click.echo("Run: python main.py (to run setup) or delta config --api-key YOUR_KEY", err=True)
        sys.exit(1)
    
    adapter = DesktopAdapter(
        api_key=config.api_key,
        data_directory=manager.config_path.parent / "data"
    )
    await adapter.initialize()
    
    gemini = GeminiClient(config.api_key, model=config.model_name)
    registry = ExtensionRegistry(manager.config_path.parent / "data" / "extensions.db")
    memory = Memory(manager.config_path.parent / "data" / "memory.db")
    
    agent = Agent(adapter, gemini, registry, memory=memory)
    
    click.echo("Processing...")
    result = await agent.run(goal)
    
    if result.success:
        click.echo(f"\n{result.response or result.message}")
    else:
        click.echo(f"Failed: {result.message}", err=True)
    
    await adapter.shutdown()


@cli.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground")
def start(foreground: bool):
    """Start the Delta daemon."""
    manager = ServiceManager()
    manager.start(foreground=foreground)


@cli.command()
def stop():
    """Stop the Delta daemon."""
    manager = ServiceManager()
    manager.stop()


@cli.command()
def restart():
    """Restart the Delta daemon."""
    manager = ServiceManager()
    manager.restart()


@cli.command()
def status():
    """Show Delta daemon status."""
    manager = ServiceManager()
    status_info = manager.status()
    
    if status_info.get("status") == "stopped":
        click.echo("Delta daemon: stopped")
    else:
        click.echo(f"Delta daemon: {status_info.get('status', 'running')}")
        if status_info.get("pid"):
            click.echo(f"  PID: {status_info['pid']}")
        if status_info.get("uptime"):
            click.echo(f"  Uptime: {status_info['uptime']}")
        if status_info.get("ghost_mode"):
            click.echo(f"  Ghost Mode: active")


@cli.command()
@click.option("--force", is_flag=True, help="Force optimization even if no issues detected")
def optimize(force: bool):
    """Run proactive self-optimization.
    
    Analyzes audit logs and fixes performance/reliability issues.
    """
    click.echo("Running self-optimization analysis...")
    asyncio.run(_run_optimization(force))


async def _run_optimization(force: bool):
    """Execute optimization loop."""
    from src.core.config import ConfigManager
    from src.adapters.desktop import DesktopAdapter
    from src.core.agent import Agent
    from src.core.gemini_client import GeminiClient
    from src.core.memory import Memory
    from src.extensions.registry import ExtensionRegistry
    from src.core.optimization import OptimizationEngine
    
    manager = ConfigManager()
    config = manager.load()
    
    if not config or not config.api_key:
        click.echo("Error: API key not configured.", err=True)
        return

    # 1. Analyze
    optimizer = OptimizationEngine()
    suggestions = optimizer.analyze_performance()
    
    if not suggestions and not force:
        click.echo("✅ System is healthy. No optimizations needed.")
        return
        
    click.echo(f"Found {len(suggestions)} optimization opportunities.")
    for s in suggestions:
        click.echo(f" - [{s.severity.upper()}] {s.suggested_action}")
        
    if not force and not click.confirm("\nDo you want to proceed with these optimizations?"):
        return
        
    # 2. Construct Goal
    goal = "Perform the following self-optimizations to improve system reliability and performance:\n"
    for s in suggestions:
        goal += f"- {s.suggested_action} (Addressing: {s.issue})\n"
    
    if not suggestions and force:
        goal = "Analyze the codebase and perform general performance optimizations on the core agent loop."
        
    # 3. Initialize Agent
    adapter = DesktopAdapter(
        api_key=config.api_key,
        data_directory=manager.config_path.parent / "data"
    )
    await adapter.initialize()
    
    gemini = GeminiClient(config.api_key, model=config.model_name)
    registry = ExtensionRegistry(manager.config_path.parent / "data" / "extensions.db")
    memory = Memory(manager.config_path.parent / "data" / "memory.db")
    
    agent = Agent(adapter, gemini, registry, memory=memory)
    
    click.echo("\nStarting optimization agent...")
    result = await agent.run(goal)
    
    if result.success:
        click.echo(f"\n✅ Optimization complete: {result.message}")
    else:
        click.echo(f"\n❌ Optimization failed: {result.message}", err=True)
    
    await adapter.shutdown()


@cli.command()
@click.option("--lines", "-n", default=50, help="Number of lines to show")
def logs(lines: int):
    """Show recent Delta logs."""
    manager = ServiceManager()
    manager.tail_logs(lines)


@cli.command()
@click.option("--api-key", help="Set Gemini API key")
@click.option("--model", help="Set default model")
@click.option("--name", help="Set user name")
@click.option("--limit", type=int, help="Set daily usage limit")
@click.option("--show", is_flag=True, help="Show current configuration")
def config(api_key: str, model: str, name: str, limit: int, show: bool):
    """Configure Delta settings."""
    from src.core.config import ConfigManager, UserConfig
    
    manager = ConfigManager()
    
    if show:
        conf = manager.load()
        if conf:
            click.echo("Current configuration:")
            click.echo(f"  User Name:   {conf.user_name}")
            click.echo(f"  Model:       {conf.model_name}")
            click.echo(f"  Usage Limit: {conf.usage_limit}")
            click.echo(f"  API Key:     {conf.api_key[:8]}..." if conf.api_key else "  API Key:     (not set)")
            click.echo(f"  Config Path: {manager.config_path}")
        else:
            click.echo("No configuration found.")
        return
    
    # Load existing or create new
    current_config = manager.load()
    
    if not current_config:
        if not api_key:
            click.echo("Error: No existing config. API Key required to create new config.")
            return
        current_config = UserConfig(api_key=api_key)
    
    # Update fields
    updates = {}
    if api_key: updates["api_key"] = api_key
    if model: updates["model_name"] = model
    if name: updates["user_name"] = name
    if limit: updates["usage_limit"] = limit
    
    if updates:
        manager.update(**updates)
        click.echo("Configuration updated.")
    else:
        click.echo("No changes specified.")


@cli.command()
def shell():
    """Start interactive Delta shell."""
    click.echo("Delta Interactive Shell")
    click.echo("Type your goals, or 'exit' to quit.\n")
    
    manager = ServiceManager()
    use_daemon = manager.is_running()
    
    if use_daemon:
        click.echo("(Connected to daemon)\n")
    else:
        click.echo("(Running directly - start daemon for better performance)\n")
    
    while True:
        try:
            goal = click.prompt("Delta", prompt_suffix=" > ")
            
            if goal.lower() in ("exit", "quit", "q"):
                break
            
            if not goal.strip():
                continue
            
            if use_daemon:
                result = manager.send_goal(goal)
                if result.get("success"):
                    click.echo(f"\n{result.get('response', result.get('message', 'Done'))}\n")
                else:
                    click.echo(f"Error: {result.get('error', result.get('message', 'Unknown'))}\n")
            else:
                asyncio.run(_run_goal_direct(goal))
                click.echo()
                
        except (KeyboardInterrupt, EOFError):
            click.echo("\nGoodbye!")
            break


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
