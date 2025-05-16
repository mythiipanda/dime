import asyncio
import os
import json
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.markdown import Markdown
from backend.agents import nba_workflow
from agno.utils.common import dataclass_to_dict
from datetime import datetime
from typing import Dict, Any, List, Optional, Set

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

def summarize_content(content: Any, max_length: int = 100) -> str:
    """Create a summarized representation of content based on its type."""
    if content is None:
        return "None"

    if isinstance(content, str):
        content_str = content.strip()
        if not content_str:
            return "Empty string"
        return f"String (len: {len(content_str)}): '{content_str[:max_length]}{'...' if len(content_str) > max_length else ''}'"
    elif isinstance(content, dict):
        if not content:
            return "Empty dictionary"
        keys = list(content.keys())
        return f"Dictionary with {len(keys)} keys: {keys[:5]}{'...' if len(keys) > 5 else ''}"
    elif isinstance(content, list):
        if not content:
            return "Empty list"
        return f"List with {len(content)} items, first item type: {type(content[0]).__name__}"
    else:
        return f"Type: {type(content).__name__}"

def create_tool_call_table(tools: List[Dict[str, Any]]) -> Table:
    """Create a rich table for tool calls."""
    table = Table(title="Tool Calls", show_header=True, header_style="bold cyan")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Args", style="yellow")
    table.add_column("Content Summary", style="blue")

    for tool in tools:
        tool_name = tool.get('tool_name', 'N/A')
        status = tool.get('status', 'N/A')
        args = safe_json_dumps(tool.get('args', {}), indent=None)
        if len(args) > 50:
            args = args[:47] + "..."

        content = tool.get('content', '')
        content_summary = summarize_content(content, max_length=50)

        table.add_row(tool_name, status, args, content_summary)

    return table

def create_event_tree(chunk_dict: Dict[str, Any]) -> Tree:
    """Create a hierarchical tree representation of an event chunk."""
    event_type = chunk_dict.get('event', 'Unknown')
    tree = Tree(f"[bold cyan]Event: {event_type}[/bold cyan]")

    # Add run_id if present
    run_id = chunk_dict.get('run_id')
    if run_id:
        tree.add(f"[yellow]Run ID:[/yellow] {run_id}")

    # Add content summary
    content = chunk_dict.get('content', '')
    content_summary = summarize_content(content)
    content_node = tree.add(f"[yellow]Content:[/yellow]")
    content_node.add(content_summary)

    # Add tools if present
    tools = chunk_dict.get('tools', [])
    if tools:
        tools_node = tree.add(f"[yellow]Tools ({len(tools)}):[/yellow]")
        for i, tool in enumerate(tools):
            tool_name = tool.get('tool_name', 'N/A')
            status = tool.get('status', 'N/A')
            tool_node = tools_node.add(f"[cyan]{i+1}. {tool_name}[/cyan] - Status: {status}")

            # Add tool arguments if present
            args = tool.get('args', {})
            if args:
                args_str = safe_json_dumps(args, indent=None)
                tool_node.add(f"Args: {args_str[:50]}{'...' if len(args_str) > 50 else ''}")

            # Add tool content summary
            tool_content = tool.get('content', '')
            if tool_content:
                tool_content_summary = summarize_content(tool_content, max_length=50)
                tool_node.add(f"Content: {tool_content_summary}")

    # Add other relevant keys
    other_keys = [k for k in chunk_dict.keys() if k not in ['event', 'content', 'run_id', 'tools', 'messages', 'id', 'type']]
    if other_keys:
        other_node = tree.add("[yellow]Other Metadata:[/yellow]")
        for k in other_keys:
            value = chunk_dict[k]
            value_summary = summarize_content(value, max_length=50)
            other_node.add(f"{k}: {value_summary}")

    return tree

def extract_data_markers(content: str) -> Dict[str, Any]:
    """Extract structured data markers from content string."""
    markers = {
        "STAT_CARD_JSON::": "STAT_CARD",
        "CHART_DATA_JSON::": "CHART_DATA",
        "TABLE_DATA_JSON::": "TABLE_DATA"
    }

    extracted = {}

    for marker, data_type in markers.items():
        if marker in content:
            try:
                marker_start = content.find(marker)
                json_start = marker_start + len(marker)
                # Try to find the end of the JSON by parsing incrementally
                json_data = content[json_start:].strip()
                extracted[data_type] = f"Found {data_type} marker at position {marker_start}"
            except Exception:
                extracted[data_type] = f"Found {data_type} marker but couldn't parse JSON"

    return extracted

async def analyze_stream(prompt: Optional[str] = None, output_format: str = "detailed",
                         filter_events: Optional[Set[str]] = None, max_chunks: Optional[int] = None):
    """
    Analyze the NBA workflow stream with enhanced output options.

    Args:
        prompt: Custom prompt to use (defaults to a comparison of Jokic and Embiid)
        output_format: Format of the output ("detailed", "summary", or "minimal")
        filter_events: Set of event types to include (e.g., {"RunStarted", "ToolCallStarted"})
        max_chunks: Maximum number of chunks to process (None for all)
    """
    console.print("\n[bold blue]Analyzing NBA Workflow Stream[/bold blue]")

    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Create output file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"nba_analysis_{timestamp}.txt")

    console.print(f"[bold yellow]Output will be saved to:[/bold yellow] {output_file}\n")

    # Use provided prompt or default
    if not prompt:
        test_prompt = """Compare Nikola Jokic and Joel Embiid's impact in 2024:

        Advanced metrics

        Team performance

        Playmaking impact"""
    else:
        test_prompt = prompt

    console.print(f"\n[yellow]Test prompt:[/yellow] {test_prompt}\n")

    # Display configuration
    config_table = Table(title="Analysis Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="yellow")
    config_table.add_row("Output Format", output_format)
    config_table.add_row("Event Filtering", str(filter_events) if filter_events else "None (showing all)")
    config_table.add_row("Max Chunks", str(max_chunks) if max_chunks else "None (showing all)")
    console.print(config_table)

    console.print("[bold green]Starting analysis...[/bold green]\n")

    with open(output_file, "w", encoding="utf-8") as f:
        # Write header and prompt to file
        f.write(f"NBA WORKFLOW ANALYSIS\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Test prompt: {test_prompt}\n\n")
        f.write(f"Configuration:\n")
        f.write(f"- Output Format: {output_format}\n")
        f.write(f"- Event Filtering: {filter_events if filter_events else 'None (showing all)'}\n")
        f.write(f"- Max Chunks: {max_chunks if max_chunks else 'None (showing all)'}\n\n")
        f.write("=" * 80 + "\n\n")

        # Track statistics
        stats = {
            "total_chunks": 0,
            "event_counts": {},
            "tool_calls": 0,
            "data_markers": {
                "STAT_CARD": 0,
                "CHART_DATA": 0,
                "TABLE_DATA": 0
            }
        }

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Processing workflow stream...", total=None)

                chunk_count = 0
                async for chunk in nba_workflow.arun(test_prompt):
                    chunk_count += 1
                    stats["total_chunks"] += 1

                    # Check if we've reached the maximum number of chunks
                    if max_chunks and chunk_count > max_chunks:
                        console.print(f"[yellow]Reached maximum chunk limit ({max_chunks}). Stopping.[/yellow]")
                        break

                    # Convert to dict for analysis
                    chunk_dict = dataclass_to_dict(chunk)
                    event_type = chunk_dict.get('event', 'Unknown')

                    # Update statistics
                    stats["event_counts"][event_type] = stats["event_counts"].get(event_type, 0) + 1
                    if chunk_dict.get('tools'):
                        stats["tool_calls"] += len(chunk_dict.get('tools', []))

                    # Check for data markers in content
                    content = chunk_dict.get('content', '')
                    if isinstance(content, str):
                        for marker, count_key in [
                            ("STAT_CARD_JSON::", "STAT_CARD"),
                            ("CHART_DATA_JSON::", "CHART_DATA"),
                            ("TABLE_DATA_JSON::", "TABLE_DATA")
                        ]:
                            if marker in content:
                                stats["data_markers"][count_key] += 1

                    # Apply event filtering if specified
                    if filter_events and event_type not in filter_events:
                        continue

                    # Write raw chunk to file first, using safe JSON serialization
                    f.write(f"CHUNK #{chunk_count} - EVENT: {event_type}\n")
                    f.write(f"RAW CHUNK:\n{safe_json_dumps(chunk_dict, indent=2)}\n\n")

                    # Update progress description
                    progress.update(task, description=f"[cyan]Processing chunk #{chunk_count} - Event: {event_type}[/cyan]")

                    # Display chunk based on output format
                    if output_format == "minimal":
                        # Minimal output - just show event type and basic info
                        console.print(f"\n[cyan]Chunk #{chunk_count} - Event:[/cyan] {event_type}")

                    elif output_format == "summary":
                        # Summary output - show compact summary
                        console.print(f"\n[bold cyan]Chunk #{chunk_count} - Event: {event_type}[/bold cyan]")

                        # Show content summary
                        content = chunk_dict.get('content', '')
                        content_summary = summarize_content(content)
                        console.print(f"[cyan]Content:[/cyan] {content_summary}")

                        # Show tool calls summary if present
                        tools = chunk_dict.get('tools', [])
                        if tools:
                            console.print(f"[cyan]Tools:[/cyan] {len(tools)} tool call(s)")
                            for tool in tools:
                                console.print(f"  - {tool.get('tool_name', 'N/A')} ({tool.get('status', 'N/A')})")

                    else:  # detailed output
                        # Create a panel with the event tree
                        event_tree = create_event_tree(chunk_dict)
                        console.print(Panel(event_tree, title=f"Chunk #{chunk_count}", border_style="cyan"))

                        # If there are tool calls, show them in a table
                        tools = chunk_dict.get('tools', [])
                        if tools:
                            console.print(create_tool_call_table(tools))

                        # Check for data markers in content
                        if isinstance(content, str):
                            data_markers = extract_data_markers(content)
                            if data_markers:
                                markers_table = Table(title="Data Markers Detected")
                                markers_table.add_column("Type", style="cyan")
                                markers_table.add_column("Info", style="yellow")
                                for marker_type, info in data_markers.items():
                                    markers_table.add_row(marker_type, info)
                                console.print(markers_table)

            # Print statistics at the end
            stats_table = Table(title="Stream Analysis Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="yellow")

            stats_table.add_row("Total Chunks Processed", str(stats["total_chunks"]))
            stats_table.add_row("Total Tool Calls", str(stats["tool_calls"]))

            # Event type breakdown
            event_breakdown = ", ".join([f"{event}: {count}" for event, count in stats["event_counts"].items()])
            stats_table.add_row("Event Types", event_breakdown)

            # Data markers
            data_markers_str = ", ".join([f"{marker}: {count}" for marker, count in stats["data_markers"].items() if count > 0])
            stats_table.add_row("Data Markers Detected", data_markers_str if data_markers_str else "None")

            console.print(stats_table)

            # Write statistics to file
            f.write("\n\nSTREAM ANALYSIS STATISTICS\n")
            f.write(f"Total Chunks: {stats['total_chunks']}\n")
            f.write(f"Total Tool Calls: {stats['tool_calls']}\n")
            f.write("Event Types:\n")
            for event, count in stats["event_counts"].items():
                f.write(f"  - {event}: {count}\n")
            f.write("Data Markers:\n")
            for marker, count in stats["data_markers"].items():
                f.write(f"  - {marker}: {count}\n")

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            f.write(f"{error_msg}\n")
            raise

    console.print(f"\n[bold green]Analysis complete![/bold green] Output saved to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze NBA Workflow Stream")
    parser.add_argument("--prompt", type=str, help="Custom prompt to use")
    parser.add_argument("--format", type=str, choices=["detailed", "summary", "minimal"],
                        default="detailed", help="Output format")
    parser.add_argument("--filter", type=str, help="Comma-separated list of event types to include")
    parser.add_argument("--max-chunks", type=int, help="Maximum number of chunks to process")

    args = parser.parse_args()

    filter_events = set(args.filter.split(",")) if args.filter else None

    asyncio.run(analyze_stream(
        prompt=args.prompt,
        output_format=args.format,
        filter_events=filter_events,
        max_chunks=args.max_chunks
    ))
