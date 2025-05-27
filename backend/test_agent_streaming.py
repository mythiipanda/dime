#!/usr/bin/env python3
"""
Test script to verify agent streaming configuration.
"""
import asyncio
import sys
import os

# Add the parent directory to the Python path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents import summer_strategy_workflow

async def test_agent_streaming():
    """Test if the summer strategy workflow agents are properly configured for streaming."""

    print("Testing individual agent streaming configuration...")

    # Test the performance analyst
    print("\n1. Testing Performance Analyst...")
    try:
        performance_analyst = summer_strategy_workflow.performance_analyst
        print(f"Performance Analyst stream config: {performance_analyst.stream}")
        print(f"Performance Analyst stream_intermediate_steps: {performance_analyst.stream_intermediate_steps}")

        # Try to call arun and see what it returns
        result = performance_analyst.arun("Test query for Boston Celtics performance analysis")
        print(f"arun result type: {type(result)}")
        print(f"Has __aiter__: {hasattr(result, '__aiter__')}")

        # Try to iterate through a few chunks
        count = 0
        async for chunk in result:
            print(f"Chunk {count}: {type(chunk)} - {chunk.content[:100] if hasattr(chunk, 'content') else str(chunk)[:100]}...")
            count += 1
            if count >= 3:  # Just test first few chunks
                break

    except Exception as e:
        print(f"Error testing performance analyst: {e}")

    print("\n2. Testing Summer Strategy Workflow...")
    try:
        # Test the workflow itself
        result = summer_strategy_workflow.arun("Boston Celtics", "2024-25")
        print(f"Workflow arun result type: {type(result)}")
        print(f"Has __aiter__: {hasattr(result, '__aiter__')}")

        # Try to iterate through a few chunks
        count = 0
        async for chunk in result:
            print(f"Workflow Chunk {count}: {type(chunk)} - {chunk.content[:100] if hasattr(chunk, 'content') else str(chunk)[:100]}...")
            count += 1
            if count >= 5:  # Just test first few chunks
                break

    except Exception as e:
        print(f"Error testing workflow: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent_streaming())
