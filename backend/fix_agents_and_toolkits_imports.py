"""
Script to fix imports in agents.py and tool_kits files.
"""
import os
import re
import glob

def fix_imports_in_file(file_path: str) -> int:
    """
    Fix imports in a Python file.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        Number of imports fixed
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix imports
    fixed_content = content
    
    # Fix 'from tool_kits.' to 'from backend.tool_kits.'
    fixed_content = re.sub(r'from tool_kits\.', r'from backend.tool_kits.', fixed_content)
    
    # Fix 'from api_tools.' to 'from backend.api_tools.'
    fixed_content = re.sub(r'from api_tools\.', r'from backend.api_tools.', fixed_content)
    
    # Fix 'from config import' to 'from backend.config import'
    fixed_content = re.sub(r'from config import', r'from backend.config import', fixed_content)
    
    # Fix 'from core.' to 'from backend.core.'
    fixed_content = re.sub(r'from core\.', r'from backend.core.', fixed_content)
    
    # Fix 'from utils.' to 'from backend.utils.'
    fixed_content = re.sub(r'from utils\.', r'from backend.utils.', fixed_content)
    
    # Count the number of changes
    num_changes = 0
    if content != fixed_content:
        num_changes = len(re.findall(r'from backend\.', fixed_content)) - len(re.findall(r'from backend\.', content))
        
        # Write the fixed content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
    
    return num_changes

def fix_imports_in_directory(directory: str) -> dict:
    """
    Fix imports in all Python files in a directory.
    
    Args:
        directory: Path to the directory
        
    Returns:
        Dictionary mapping file paths to number of imports fixed
    """
    # Get all Python files in the directory
    python_files = glob.glob(os.path.join(directory, '*.py'))
    
    # Fix imports in each file
    results = {}
    for file_path in python_files:
        num_fixed = fix_imports_in_file(file_path)
        if num_fixed > 0:
            results[file_path] = num_fixed
    
    return results

def main():
    """
    Fix imports in agents.py and all Python files in the tool_kits directory.
    """
    # Fix imports in agents.py
    agents_file = 'agents.py'
    num_fixed_agents = fix_imports_in_file(agents_file)
    if num_fixed_agents > 0:
        print(f"Fixed {num_fixed_agents} imports in {agents_file}")
    
    # Fix imports in the tool_kits directory
    results = fix_imports_in_directory('tool_kits')
    
    # Print the results
    print(f"Fixed imports in {len(results)} files in tool_kits:")
    for file_path, num_fixed in results.items():
        print(f"{file_path}: {num_fixed} imports fixed")

if __name__ == "__main__":
    main()
