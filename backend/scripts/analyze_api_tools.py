"""
Script to analyze the contents of backend/api_tools directory and help identify tools
for updating tool_kits and agents.py configurations.
"""
import os
import sys
import ast
from pathlib import Path

def extract_function_info(node):
    """Extract information about a function definition."""
    # Get docstring if it exists
    docstring = ast.get_docstring(node)
    
    # Get function parameters
    params = []
    for arg in node.args.args:
        # Get type annotation if it exists
        type_annotation = None
        if arg.annotation:
            type_annotation = ast.unparse(arg.annotation)
        params.append({
            'name': arg.arg,
            'type': type_annotation
        })
    
    # Get return type if it exists
    returns = None
    if node.returns:
        returns = ast.unparse(node.returns)
    
    return {
        'name': node.name,
        'params': params,
        'returns': returns,
        'docstring': docstring
    }

def analyze_python_file(file_path):
    """Analyze a Python file and extract information about its functions."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Error parsing {file_path}: {e}")
        return None
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Only include functions that end with "_logic"
            if node.name.endswith('_logic'):
                functions.append(extract_function_info(node))
    
    return functions

def analyze_api_tools_directory(api_tools_dir):
    """Analyze all Python files in the api_tools directory."""
    results = {}
    
    for file in os.listdir(api_tools_dir):
        if file.endswith('.py') and not file.startswith('__'):
            file_path = os.path.join(api_tools_dir, file)
            print(f"\nAnalyzing {file}...")
            functions = analyze_python_file(file_path)
            if functions:
                results[file] = functions
    
    return results

def generate_report(results):
    """Generate a detailed report of the analysis."""
    report = []
    report.append("# API Tools Analysis Report\n")
    
    # Generate function mapping for tool_kits
    report.append("## Function to Tool Mapping\n")
    report.append("This section maps api_tools logic functions to tool_kits wrappers:\n\n")
    
    for file, functions in results.items():
        report.append(f"\n### {file}\n")
        for func in functions:
            # Clean up function details for the report
            func_name = func['name']
            params_str = []
            for param in func['params']:
                param_type = f": {param['type']}" if param['type'] else ""
                params_str.append(f"{param['name']}{param_type}")
            
            returns_str = f" -> {func['returns']}" if func['returns'] else ""
            
            report.append(f"#### {func_name}")
            report.append(f"```python")
            report.append(f"def {func_name}({', '.join(params_str)}){returns_str}:")
            if func['docstring']:
                report.append(f"    \"\"\"{func['docstring']}\"\"\"")
            report.append("```\n")
            
            # Suggest tool name and category
            tool_name = func_name.replace('fetch_', '').replace('_logic', '')
            if 'player' in tool_name:
                category = 'player_tools'
            elif 'team' in tool_name:
                category = 'team_tools'
            elif 'game' in tool_name:
                category = 'game_tools'
            elif 'league' in tool_name:
                category = 'league_tools'
            else:
                category = 'misc_tools'
            
            report.append(f"Suggested Tool Configuration:")
            report.append(f"```python")
            report.append(f"# Add to backend/tool_kits/{category}.py")
            report.append(f"@tool")
            report.append(f"def get_{tool_name}(...):  # Add parameters based on {func_name}")
            report.append(f"    return {func_name}(...)")
            report.append(f"```\n")
    
    # Generate updates for agents.py
    report.append("\n## Updates for agents.py\n")
    report.append("The following tools should be imported and added to the `nba_tools` list:\n\n")
    
    tool_imports = {}
    for file, functions in results.items():
        for func in functions:
            tool_name = func['name'].replace('fetch_', '').replace('_logic', '')
            if 'player' in tool_name:
                category = 'player_tools'
            elif 'team' in tool_name:
                category = 'team_tools'
            elif 'game' in tool_name:
                category = 'game_tools'
            elif 'league' in tool_name:
                category = 'league_tools'
            else:
                category = 'misc_tools'
            
            if category not in tool_imports:
                tool_imports[category] = []
            tool_imports[category].append(f"get_{tool_name}")
    
    for category, tools in tool_imports.items():
        report.append(f"\n### {category}.py imports\n```python")
        report.append(f"from backend.tool_kits.{category} import (")
        for tool in sorted(tools):
            report.append(f"    {tool},")
        report.append(")")
        report.append("```\n")
    
    return "\n".join(report)

def main():
    """Main function to run the analysis."""
    # Get the directory containing api_tools
    script_dir = Path(__file__).parent.parent
    api_tools_dir = script_dir / 'api_tools'
    
    if not api_tools_dir.exists():
        print(f"Error: {api_tools_dir} directory not found")
        sys.exit(1)
    
    print(f"Analyzing api_tools directory: {api_tools_dir}")
    results = analyze_api_tools_directory(str(api_tools_dir))
    
    # Generate and save the report
    report = generate_report(results)
    report_path = script_dir / 'api_tools_analysis.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nAnalysis complete! Report saved to: {report_path}")

if __name__ == '__main__':
    main()