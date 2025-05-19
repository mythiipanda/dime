"""
Test script for path_utils.py to verify path handling.
"""
import os
import sys
import logging
from utils.path_utils import (
    get_cache_dir,
    get_cache_file_path,
    get_relative_cache_path,
    ensure_dir_exists,
    BACKEND_DIR,
    CACHE_DIR
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_path_constants():
    """Test the path constants."""
    logger.info("Testing path constants...")
    
    # Check that BACKEND_DIR exists
    assert os.path.exists(BACKEND_DIR), f"BACKEND_DIR does not exist: {BACKEND_DIR}"
    logger.info(f"BACKEND_DIR exists: {BACKEND_DIR}")
    
    # Check that CACHE_DIR exists or can be created
    ensure_dir_exists(CACHE_DIR)
    assert os.path.exists(CACHE_DIR), f"CACHE_DIR does not exist: {CACHE_DIR}"
    logger.info(f"CACHE_DIR exists: {CACHE_DIR}")
    
    return True

def test_ensure_dir_exists():
    """Test the ensure_dir_exists function."""
    logger.info("Testing ensure_dir_exists...")
    
    # Create a test directory
    test_dir = os.path.join(CACHE_DIR, "test_dir")
    ensure_dir_exists(test_dir)
    assert os.path.exists(test_dir), f"Test directory does not exist: {test_dir}"
    logger.info(f"Test directory exists: {test_dir}")
    
    # Create a nested test directory
    nested_test_dir = os.path.join(test_dir, "nested", "test", "dir")
    ensure_dir_exists(nested_test_dir)
    assert os.path.exists(nested_test_dir), f"Nested test directory does not exist: {nested_test_dir}"
    logger.info(f"Nested test directory exists: {nested_test_dir}")
    
    return True

def test_get_cache_dir():
    """Test the get_cache_dir function."""
    logger.info("Testing get_cache_dir...")
    
    # Get the cache directory
    cache_dir = get_cache_dir()
    assert os.path.exists(cache_dir), f"Cache directory does not exist: {cache_dir}"
    logger.info(f"Cache directory exists: {cache_dir}")
    
    # Get a subdirectory of the cache directory
    subdirectory = "test_subdirectory"
    cache_subdir = get_cache_dir(subdirectory)
    assert os.path.exists(cache_subdir), f"Cache subdirectory does not exist: {cache_subdir}"
    logger.info(f"Cache subdirectory exists: {cache_subdir}")
    
    return True

def test_get_cache_file_path():
    """Test the get_cache_file_path function."""
    logger.info("Testing get_cache_file_path...")
    
    # Get a file path in the cache directory
    filename = "test_file.txt"
    file_path = get_cache_file_path(filename)
    logger.info(f"File path: {file_path}")
    
    # Get a file path in a subdirectory of the cache directory
    subdirectory = "test_subdirectory"
    file_path_in_subdir = get_cache_file_path(filename, subdirectory)
    logger.info(f"File path in subdirectory: {file_path_in_subdir}")
    
    # Write to the file to verify the path is valid
    with open(file_path, "w") as f:
        f.write("Test content")
    assert os.path.exists(file_path), f"File does not exist: {file_path}"
    logger.info(f"File exists: {file_path}")
    
    # Write to the file in the subdirectory to verify the path is valid
    with open(file_path_in_subdir, "w") as f:
        f.write("Test content in subdirectory")
    assert os.path.exists(file_path_in_subdir), f"File in subdirectory does not exist: {file_path_in_subdir}"
    logger.info(f"File in subdirectory exists: {file_path_in_subdir}")
    
    return True

def test_get_relative_cache_path():
    """Test the get_relative_cache_path function."""
    logger.info("Testing get_relative_cache_path...")
    
    # Get a relative path in the cache directory
    filename = "test_relative_file.txt"
    relative_path = get_relative_cache_path(filename)
    logger.info(f"Relative path: {relative_path}")
    
    # Get a relative path in a subdirectory of the cache directory
    subdirectory = "test_relative_subdirectory"
    relative_path_in_subdir = get_relative_cache_path(filename, subdirectory)
    logger.info(f"Relative path in subdirectory: {relative_path_in_subdir}")
    
    # Verify that the relative paths are correct
    assert relative_path == os.path.join("cache", filename), f"Relative path is incorrect: {relative_path}"
    assert relative_path_in_subdir == os.path.join("cache", subdirectory, filename), f"Relative path in subdirectory is incorrect: {relative_path_in_subdir}"
    
    # Verify that the absolute paths can be constructed from the relative paths
    absolute_path = os.path.join(BACKEND_DIR, relative_path)
    absolute_path_in_subdir = os.path.join(BACKEND_DIR, relative_path_in_subdir)
    
    # Ensure the directories exist
    ensure_dir_exists(os.path.dirname(absolute_path))
    ensure_dir_exists(os.path.dirname(absolute_path_in_subdir))
    
    # Write to the files to verify the paths are valid
    with open(absolute_path, "w") as f:
        f.write("Test relative content")
    assert os.path.exists(absolute_path), f"File does not exist: {absolute_path}"
    logger.info(f"File exists: {absolute_path}")
    
    with open(absolute_path_in_subdir, "w") as f:
        f.write("Test relative content in subdirectory")
    assert os.path.exists(absolute_path_in_subdir), f"File in subdirectory does not exist: {absolute_path_in_subdir}"
    logger.info(f"File in subdirectory exists: {absolute_path_in_subdir}")
    
    return True

def run_all_tests():
    """Run all tests."""
    logger.info("Running all tests...")
    
    tests = [
        test_path_constants,
        test_ensure_dir_exists,
        test_get_cache_dir,
        test_get_cache_file_path,
        test_get_relative_cache_path
    ]
    
    all_passed = True
    for test in tests:
        try:
            result = test()
            if not result:
                all_passed = False
                logger.error(f"Test {test.__name__} failed")
        except Exception as e:
            all_passed = False
            logger.error(f"Test {test.__name__} raised an exception: {e}", exc_info=True)
    
    if all_passed:
        logger.info("All tests passed!")
    else:
        logger.error("Some tests failed")
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
