import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

print("Loading agents...")

try:
    # Import agents to trigger their initialization
    from agents import analysis_agent, data_aggregator_agent, data_normalizer_agent
    
    print("\n--- Agent Definitions ---")
    print(f"Analysis Agent: {analysis_agent.name if analysis_agent else 'Not loaded'}")
    print(f"Data Aggregator Agent: {data_aggregator_agent.name if data_aggregator_agent else 'Not loaded'}")
    print(f"Data Normalizer Agent: {data_normalizer_agent.name if data_normalizer_agent else 'Not loaded'}")
    
    print("\nSuccessfully initialized agents from agents.py!")
    print("\nNOTE: This script only checks initialization.")
    print("Further testing requires API keys (e.g., GOOGLE_API_KEY for Gemini) in the .env file.")
    
except ImportError as e:
    print(f"\nError importing agents: {e}")
    print("Please check dependencies and file paths.")
except Exception as e:
    print(f"\nAn error occurred during agent initialization: {e}")
    print("Ensure API keys are correctly set in .env if required by models.")