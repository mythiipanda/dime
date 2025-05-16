import asyncio
from rich.console import Console
from rich.markdown import Markdown
from backend.agents import nba_workflow
from agno.run.response import RunEvent

console = Console()

async def test_workflow():
    console.print("\n[bold blue]Testing NBA Analysis Workflow[/bold blue]")

    test_prompt = """Compare Nikola Jokic and Joel Embiid's impact in the 2024 season:

Advanced metrics and efficiency

Team performance with/without them

Playmaking and scoring patterns

Impact on teammate efficiency"""

    console.print(f"\n[yellow]Testing prompt:[/yellow] {test_prompt}\n")
    console.print("[bold green]Starting workflow...[/bold green]\n")

    try:
        async for response in nba_workflow.arun(test_prompt):
            # Print event information
            if response.event:
                console.print(f"[dim]Event: {response.event}[/dim]")

            # Print content for specific events
            if response.event in [RunEvent.run_response, RunEvent.run_completed]:
                if response.content:
                    try:
                        md = Markdown(response.content)
                        console.print(md)
                    except:
                        console.print(response.content)
            
            # Print tool information
            if response.event == RunEvent.tool_call_completed and response.tools:
                for tool in response.tools:
                    console.print(f"[dim]Tool completed: {tool.get('tool_name')}[/dim]")
        
        console.print("---")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise e

if __name__ == "__main__":
    asyncio.run(test_workflow())
