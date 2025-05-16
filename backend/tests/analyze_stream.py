import asyncio
import os
import json
from rich.console import Console
from backend.agents import nba_workflow
from agno.utils.common import dataclass_to_dict
from datetime import datetime

console = Console()

# Custom JSON encoder to handle non-serializable objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            # For objects that can't be serialized, convert to string representation
            return f"<Non-serializable object of type {type(obj).__name__}>"

def safe_json_dumps(obj, **kwargs):
    """Safely convert an object to JSON string, handling non-serializable objects."""
    try:
        return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)
    except Exception as e:
        # If even the custom encoder fails, return a fallback string
        return f"<Could not serialize object: {str(e)}>"

async def analyze_stream():
    console.print("\n[bold blue]Analyzing NBA Workflow Stream[/bold blue]")

    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Create output file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"nba_analysis_{timestamp}.txt")

    console.print(f"[bold yellow]Output will be saved to:[/bold yellow] {output_file}\n")

    test_prompt = """Compare Nikola Jokic and Joel Embiid's impact in 2024:

    Advanced metrics

    Team performance

    Playmaking impact"""

    console.print(f"\n[yellow]Test prompt:[/yellow] {test_prompt}\n")
    console.print("[bold green]Starting analysis...[/bold green]\n")

    with open(output_file, "w", encoding="utf-8") as f:
        # Write header and prompt to file
        f.write(f"NBA WORKFLOW ANALYSIS\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Test prompt: {test_prompt}\n\n")
        f.write("=" * 80 + "\n\n")

        try:
            async for chunk in nba_workflow.arun(test_prompt):
                # Convert to dict for analysis
                chunk_dict = dataclass_to_dict(chunk)

                # Write raw chunk to file first, using safe JSON serialization
                f.write(f"RAW CHUNK:\n{safe_json_dumps(chunk_dict, indent=2)}\n\n")

                # --- MODIFIED SECTION FOR CONSOLE OUTPUT ---
                console.print("\n--- Summarized Chunk ---")
                console.print(f"[cyan]Event:[/cyan] {chunk_dict.get('event')}")
                
                content = chunk_dict.get('content', '')
                content_summary = ""
                if isinstance(content, str):
                    content_summary = f"String (len: {len(content)}): '{content[:100]}{'...' if len(content) > 100 else ''}'"
                elif isinstance(content, dict):
                    content_summary = f"Dictionary (keys: {list(content.keys())[:5]}{'...' if len(content.keys()) > 5 else ''})"
                elif isinstance(content, list):
                    content_summary = f"List (len: {len(content)}, first item type: {type(content[0]).__name__ if content else 'N/A'})"
                else:
                    content_summary = f"Type: {type(content).__name__}"
                console.print(f"[cyan]Content Summary:[/cyan] {content_summary}")

                run_id = chunk_dict.get('run_id')
                if run_id:
                    console.print(f"[cyan]Run ID:[/cyan] {run_id}")

                tools = chunk_dict.get('tools')
                if tools:
                    console.print(f"[cyan]Tools ({len(tools)}):[/cyan]")
                    for tool_call in tools:
                        tool_name = tool_call.get('tool_name', 'N/A')
                        tool_status = tool_call.get('status', 'N/A') # Assuming status might be part of tool_call
                        tool_content = tool_call.get('content', '')
                        tool_content_summary = ""
                        if isinstance(tool_content, str):
                            tool_content_summary = f"String (len: {len(tool_content)}): '{tool_content[:50]}{'...' if len(tool_content) > 50 else ''}'"
                        elif tool_content: # If not string but not empty
                             tool_content_summary = f"Type: {type(tool_content).__name__}"
                        console.print(f"  - Name: {tool_name}, Status: {tool_status}, Content: {tool_content_summary}")
                
                # Print other relevant top-level keys if they exist
                other_keys = [k for k in chunk_dict.keys() if k not in ['event', 'content', 'run_id', 'tools', 'messages', 'id', 'type']]
                if other_keys:
                    console.print(f"[cyan]Other Keys:[/cyan] {other_keys}")
                    for k in other_keys:
                         console.print(f"  - {k}: {str(chunk_dict[k])[:100]}{'...' if len(str(chunk_dict[k])) > 100 else ''}")
                console.print("--- End Summarized Chunk ---")
                # --- END MODIFIED SECTION ---

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            f.write(f"{error_msg}\n")
            raise

    console.print(f"\n[bold green]Analysis complete![/bold green] Output saved to: {output_file}")

if __name__ == "__main__":
    asyncio.run(analyze_stream())
