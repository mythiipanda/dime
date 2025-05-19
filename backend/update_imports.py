"""
Script to update imports in Python files to use relative imports.
"""
import os
import re
import glob
from typing import List, Dict, Tuple

def get_relative_import_path(from_file: str, to_module: str) -> str:
    """
    Calculate the relative import path from one file to another module.
    
    Args:
        from_file: Path to the file containing the import
        to_module: Module being imported (e.g., 'backend.config')
        
    Returns:
        Relative import path (e.g., '..config')
    """
    # Get the directory of the file containing the import
    from_dir = os.path.dirname(from_file)
    
    # Split the module path into components
    module_parts = to_module.split('.')
    
    # If the module starts with 'backend', remove it
    if module_parts[0] == 'backend':
        module_parts = module_parts[1:]
    
    # Calculate the relative path
    from_parts = from_dir.split(os.sep)
    
    # Find the 'backend' directory in the from_parts
    try:
        backend_index = from_parts.index('backend')
    except ValueError:
        # If 'backend' is not in from_parts, assume we're at the root
        backend_index = -1
    
    # Calculate the number of parent directories to go up
    if backend_index >= 0:
        depth = len(from_parts) - backend_index - 1
    else:
        depth = 0
    
    # Construct the relative import path
    if depth == 0:
        # If we're at the root, just use the module parts
        rel_path = '.'.join(module_parts)
    else:
        # Otherwise, go up the required number of directories
        rel_path = '.' * depth + '.' + '.'.join(module_parts)
    
    return rel_path

def update_imports_in_file(file_path: str) -> Tuple[int, List[str]]:
    """
    Update imports in a Python file to use relative imports.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        Tuple of (number of imports updated, list of updated imports)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all 'from ' imports
    import_pattern = re.compile(r'from\s+(backend\.[^\s]+)\s+import')
    matches = import_pattern.findall(content)
    
    # Keep track of updated imports
    updated_imports = []
    
    # Replace each import with a relative import
    for match in matches:
        rel_path = get_relative_import_path(file_path, match)
        content = content.replace(f'from {match} import', f'from {rel_path} import')
        updated_imports.append(f'{match} -> {rel_path}')
    
    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return len(updated_imports), updated_imports

def update_imports_in_directory(directory: str) -> Dict[str, Tuple[int, List[str]]]:
    """
    Update imports in all Python files in a directory to use relative imports.
    
    Args:
        directory: Path to the directory
        
    Returns:
        Dictionary mapping file paths to tuples of (number of imports updated, list of updated imports)
    """
    # Get all Python files in the directory
    python_files = glob.glob(os.path.join(directory, '**', '*.py'), recursive=True)
    
    # Update imports in each file
    results = {}
    for file_path in python_files:
        num_updated, updated_imports = update_imports_in_file(file_path)
        if num_updated > 0:
            results[file_path] = (num_updated, updated_imports)
    
    return results

def main():
    """
    Update imports in all Python files in the backend directory to use relative imports.
    """
    # Update imports in the backend directory
    results = update_imports_in_directory('.')
    
    # Print the results
    print(f"Updated imports in {len(results)} files:")
    for file_path, (num_updated, updated_imports) in results.items():
        print(f"{file_path}: {num_updated} imports updated")
        for updated_import in updated_imports:
            print(f"  {updated_import}")

if __name__ == "__main__":
    main()
