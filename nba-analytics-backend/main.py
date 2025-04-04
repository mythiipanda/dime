from fastapi import FastAPI
import uvicorn

# Import defined agents
from agents import analysis_agent, data_aggregator_agent, data_normalizer_agent # Use absolute import

app = FastAPI(title="NBA Analytics Backend")

@app.get("/")
async def read_root():
    return {"message": "NBA Analytics Backend using Agno"}

# --- Agent Interaction Endpoints ---

# Example: Endpoint to trigger analysis (will need input data structure later)
@app.post("/analyze")
async def analyze_data(request_data: dict):
    # In a real scenario, request_data would contain the structured data
    # and the specific analysis query (e.g., "compare player A and B")
    query = request_data.get("query", "Provide a general analysis of the data.")
    data_input = request_data.get("data", {}) # This data would come from normalization
    
    # Using arun for async execution if needed, or run for sync
    # Assuming analysis_agent needs the data passed directly for now
    try:
        # This is a simplified interaction. A workflow would manage data flow better.
        result = await analysis_agent.arun(f"{query}. Data: {str(data_input)}")
        return {"analysis": result.response}
    except Exception as e:
        return {"error": str(e)}

# Placeholder: Endpoint to trigger data aggregation
@app.post("/fetch_data")
async def fetch_data(request_data: dict):
    # request_data might specify API source, player ID, game ID, etc.
    target = request_data.get("target", "latest player stats")
    try:
        # Simplified - aggregator would use tools based on 'target'
        result = await data_aggregator_agent.arun(f"Fetch data for: {target}")
        # This raw data would then likely be passed to the normalizer
        return {"raw_data": result.response} # Or return the actual structured data if tool returns it
    except Exception as e:
        return {"error": str(e)}

# Placeholder: Endpoint to trigger data normalization (might be internal workflow step)
@app.post("/normalize_data")
async def normalize_data(raw_data: dict):
    # raw_data would be the output from the aggregator
    try:
        # Simplified - normalizer transforms the input
        result = await data_normalizer_agent.arun(f"Normalize this data: {str(raw_data)}")
        return {"normalized_data": result.response} # Or return the actual structured data
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)