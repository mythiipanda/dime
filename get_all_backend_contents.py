import os

def get_file_contents(directory):
    """Reads and returns the content of all Python files in a given directory."""
    contents = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        contents[file_path] = f.read()
                except Exception as e:
                    contents[file_path] = f"Error reading file: {e}"
    return contents

if __name__ == "__main__":
    api_tools_dir = 'backend/api_tools/'
    toolkits_dir = 'backend/langgraph_agent/toolkits/'
    output_file = 'backend_contents.txt'

    with open(output_file, 'w', encoding='utf-8') as f_out:
        f_out.write(f"--- Contents of {api_tools_dir} ---\n\n")
        api_contents = get_file_contents(api_tools_dir)
        for path, content in api_contents.items():
            f_out.write(f"File: {path}\n{'='*len(path)}\n{content}\n\n")

        f_out.write(f"--- Contents of {toolkits_dir} ---\n\n")
        toolkit_contents = get_file_contents(toolkits_dir)
        for path, content in toolkit_contents.items():
            f_out.write(f"File: {path}\n{'='*len(path)}\n{content}\n\n")

    print(f"All backend API tool and toolkit contents saved to {output_file}")