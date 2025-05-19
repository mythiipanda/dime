"""
Script to fix imports in api_tools files.
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
    
    # Fix 'from config import' to 'from ..config import'
    fixed_content = re.sub(r'from config import', r'from ..config import', fixed_content)
    
    # Fix 'from core.errors import' to 'from ..core.errors import'
    fixed_content = re.sub(r'from core\.errors import', r'from ..core.errors import', fixed_content)
    
    # Fix 'from utils.validation import' to 'from ..utils.validation import'
    fixed_content = re.sub(r'from utils\.validation import', r'from ..utils.validation import', fixed_content)
    
    # Fix 'from api_tools.utils import' to 'from .utils import'
    fixed_content = re.sub(r'from api_tools\.utils import', r'from .utils import', fixed_content)
    
    # Fix other api_tools imports
    fixed_content = re.sub(r'from api_tools\.([^\s]+) import', r'from .\1 import', fixed_content)
    
    # Count the number of changes
    num_changes = 0
    if content != fixed_content:
        num_changes = len(re.findall(r'from \.\.', fixed_content)) + len(re.findall(r'from \.', fixed_content))
        
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
    Fix imports in all Python files in the api_tools directory.
    """
    # Fix imports in the api_tools directory
    results = fix_imports_in_directory('api_tools')
    
    # Print the results
    print(f"Fixed imports in {len(results)} files:")
    for file_path, num_fixed in results.items():
        print(f"{file_path}: {num_fixed} imports fixed")

if __name__ == "__main__":
    main()
