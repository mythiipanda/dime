"""
Script to run a smoke test with the correct Python path setup.
"""
import os
import sys
import importlib.util
import argparse

def run_test(test_file):
    """
    Run a smoke test with the correct Python path setup.
    
    Args:
        test_file: Path to the test file
    """
    # Add the project root directory to the Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(project_root))
    
    # Import the test module
    module_name = os.path.splitext(os.path.basename(test_file))[0]
    spec = importlib.util.spec_from_file_location(module_name, test_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Run the test
    if hasattr(module, 'run_all_tests'):
        success = module.run_all_tests()
        return 0 if success else 1
    else:
        print(f"Error: Test file {test_file} does not have a run_all_tests function.")
        return 1

def main():
    """
    Parse command line arguments and run the test.
    """
    parser = argparse.ArgumentParser(description='Run a smoke test with the correct Python path setup.')
    parser.add_argument('test_file', help='Path to the test file')
    args = parser.parse_args()
    
    return run_test(args.test_file)

if __name__ == "__main__":
    sys.exit(main())
