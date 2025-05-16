
import asyncio
from rich.console import Console
from backend.agents import nba_workflow
from agno.utils.common import dataclass_to_dict

console = Console()

async def analyze_stream():
    console.print("\n[bold blue]Analyzing NBA Workflow Stream[/bold blue]")

    test_prompt = """Compare Nikola Jokic and Joel Embiid's impact in 2024:

    Advanced metrics

    Team performance

    Playmaking impact"""

    console.print(f"\n[yellow]Test prompt:[/yellow] {test_prompt}\n")
    console.print("[bold green]Starting analysis...[/bold green]\n")

    try:
        async for chunk in nba_workflow.arun(test_prompt):
            # Convert to dict for analysis
            chunk_dict = dataclass_to_dict(chunk)
            print(chunk_dict)
            # Print stream analysis
            console.print("\n[cyan]Stream Chunk:[/cyan]")
            console.print("[magenta]Event Type:[/magenta]", chunk_dict.get("event", "No event"))
            
            if chunk_dict.get("content"):
                console.print("[magenta]Content:[/magenta]")
                console.print(chunk_dict["content"])
            
            if chunk_dict.get("tools"):
                console.print("[magenta]Tools:[/magenta]")
                for tool in chunk_dict["tools"]:
                    console.print(f"- {tool.get('tool_name', 'Unknown tool')}")
                    if "content" in tool:
                        console.print(f"  Result: {tool['content'][:200]}...")
            
                console.print("[dim]" + "-" * 80 + "[/dim]\n")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(analyze_stream())