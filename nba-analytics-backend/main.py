from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn

# Import defined agents
from agents import analysis_agent, data_aggregator_agent, data_normalizer_agent

app = FastAPI(title="NBA Analytics Backend")

@app.get("/")
async def read_root():
    return {"message": "NBA Analytics Backend using Agno"}

# --- Agent Interaction Endpoints ---

# --- Request Models ---
class AnalyzeRequest(BaseModel):
    query: str = "Provide a general analysis of the data."
    data: Dict[str, Any] # Represents the normalized data input

class FetchRequest(BaseModel):
    target: str = "latest player stats"
    params: Dict[str, Any] = {} # Parameters for the API call

class NormalizeRequest(BaseModel):
    raw_data: Dict[str, Any] # Represents the raw data from aggregator

# --- Agent Interaction Endpoints ---

# Example: Endpoint to trigger analysis
@app.post("/analyze")
async def analyze_data(request: AnalyzeRequest):
    # In a real scenario, request_data would contain the structured data
    # and the specific analysis query (e.g., "compare player A and B")
    query = request.query
    data_input = request.data # This data would come from normalization
    
    # Using arun for async execution if needed, or run for sync
    # Assuming analysis_agent needs the data passed directly for now
    try:
        # This is a simplified interaction. A workflow would manage data flow better.
        # In a real workflow, data_input would be structured and validated
        result = await analysis_agent.arun(f"{query}. Analyze the following data: {str(data_input)}")
        if result and hasattr(result, 'response'):
             return {"analysis": result.response}
        else:
             raise HTTPException(status_code=500, detail="Analysis agent did not return a valid response.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

# Placeholder: Endpoint to trigger data aggregation
# Placeholder: Endpoint to trigger data aggregation
@app.post("/fetch_data")
async def fetch_data(request: FetchRequest):
    # request.target might specify API source, player ID, game ID, etc.
    # request.params would contain specific filters like player_id=123
    target = request.target
    params = request.params
    try:
        # Simplified - aggregator would use tools based on 'target'
        # Simplified - aggregator would use tools based on 'target' and 'params'
        # Example: result = await data_aggregator_agent.arun(f"Fetch data for: {target} with params {params}")
        # For now, just simulate the call structure
        result = await data_aggregator_agent.arun(f"Simulate fetching data for: {target} with params {params}")
        if result and hasattr(result, 'response'):
            # In reality, the agent's tool would return structured data, not just the response text
            return {"raw_data_simulation_result": result.response}
        else:
            raise HTTPException(status_code=500, detail="Data aggregator agent did not return a valid response.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetching error: {str(e)}")

# Placeholder: Endpoint to trigger data normalization (might be internal workflow step)
# Placeholder: Endpoint to trigger data normalization (might be internal workflow step)
@app.post("/normalize_data")
async def normalize_data(request: NormalizeRequest):
    # raw_data would be the output from the aggregator
    raw_data = request.raw_data
    try:
        # Simplified - normalizer transforms the input
        # Simplified - normalizer transforms the input
        result = await data_normalizer_agent.arun(f"Simulate normalizing this data: {str(raw_data)}")
        if result and hasattr(result, 'response'):
             # In reality, the agent would return structured normalized data
            return {"normalized_data_simulation_result": result.response}
        else:
            raise HTTPException(status_code=500, detail="Data normalizer agent did not return a valid response.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data normalization error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)